"""Safe official headless CLI adapters (never direct model HTTP/API access).

The user-selected official CLI owns model and reasoning choices. Provider tools
must not control Android: only the preserved ARTEMIS engine executes actions.
Offline contract tests cover transport shapes, not paid inference behavior.
"""

import base64
import json
import os
from pathlib import Path

from callisto.llm_adapter.errors import CLIAuthenticationError, CLIError, CLIProtocolError, UnsupportedCapability
from callisto.llm_adapter.discovery import discover_executable, executable_command


def command_for(provider, model, directory, images, schema_path, reasoning_effort=None):
    if os.environ.get("CALLISTO_FORBID_LIVE_CLI") == "1":
        raise CLIError("Live AI CLI execution is forbidden in this environment")
    if provider not in ("codex", "claude", "gemini"):
        raise UnsupportedCapability(f"CLI provider {provider!r} is not implemented")
    launcher = executable_command(provider)
    if not launcher:
        if not discover_executable(provider):
            raise CLIError(f"Install and log in to {provider} CLI on the Callisto machine")
        raise UnsupportedCapability(
            f"{provider} CLI launcher is not a native executable or a verified npm/Node entrypoint"
        )
    if provider == "codex":
        # Do NOT use --ignore-user-config: it discards the user's selected CLI defaults.
        # Disable CLI-owned effects and explicitly request a read-only sandbox.
        command = [*launcher, "exec", "--ignore-rules", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only",
                   "--disable", "shell_tool", "--disable", "apps",
                   "--disable", "plugins", "--disable", "hooks",
                   "--disable", "multi_agent", "-c", 'web_search="disabled"',
                   "--json", "--output-schema", str(schema_path),
                   "-C", str(directory)]
        for image in images:
            command += ["--image", image]
        return [*command, "-"]
    if provider == "claude":
        # Stream-json stdin carries real multimodal image blocks; never ask the
        # provider to use a shell/Read tool for screenshots.
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        return [*launcher, "-p", "--output-format", "json",
                "--input-format", "stream-json",
                "--json-schema", json.dumps(schema, separators=(",", ":")),
                "--tools", "", "--disallowedTools", "mcp__*",
                "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                "--permission-mode", "dontAsk",
                "--safe-mode", "--no-session-persistence"]
    # Gemini's @file image-context injection is implemented by the official CLI.
    # Plan mode is read-only; the temporary workspace policy rejects tool usage.
    policy = Path(directory) / ".gemini" / "policies"
    policy.mkdir(parents=True, exist_ok=True)
    (policy / "callisto-deny.toml").write_text(
        '[[rule]]\ntoolName = "*"\ndecision = "deny"\npriority = 999\n',
        encoding="utf-8",
    )
    return [*launcher, "--prompt", "", "--output-format", "stream-json",
            "--approval-mode", "plan", "--skip-trust"]


def build_stdin(provider, prompt, images):
    """Emit the official provider's supported input format without losing images."""
    if provider == "claude":
        content = [{"type": "text", "text": prompt}]
        for filename in images:
            path = Path(filename)
            mime = {".png": "image/png", ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(path.suffix.lower())
            if mime is None:
                raise UnsupportedCapability("Unsupported Claude screenshot type")
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": mime,
                "data": base64.b64encode(path.read_bytes()).decode("ascii")}})
        payload = json.dumps({"type": "user", "message": {"role": "user", "content": content}},
                             ensure_ascii=False, separators=(",", ":")) + "\n"
        # Claude's piped-input limit is documented as 10 MB. Never silently
        # drop screenshots or truncate conversation history.
        if len(payload.encode("utf-8")) > 9_500_000:
            raise CLIProtocolError("Claude CLI multimodal stdin exceeds its size limit")
        return payload
    if provider == "gemini" and images:
        # The headless CLI expands @paths to multimodal parts from the same
        # temporary workspace. Do not place base64 in a text prompt.
        paths = "\n".join(f"@{Path(p).as_posix()}" for p in images)
        return prompt + "\n\nAttached image files (numbered in history order):\n" + paths
    return prompt


def _gemini_usage(stats):
    if not isinstance(stats, dict):
        return {}
    models = stats.get("models", {})
    if not isinstance(models, dict):
        return {}
    input_values, output_values = [], []
    for model in models.values():
        tokens = model.get("tokens", {}) if isinstance(model, dict) else {}
        if not isinstance(tokens, dict):
            continue
        for destination, keys in ((input_values, ("prompt", "promptTokens")),
                                   (output_values, ("response", "candidates", "outputTokens"))):
            value = next((tokens[k] for k in keys
                          if isinstance(tokens.get(k), int) and not isinstance(tokens[k], bool)
                          and tokens[k] >= 0), None)
            if value is not None:
                destination.append(value)
    usage = {}
    if input_values:
        usage["input_tokens"] = sum(input_values)
    if output_values:
        usage["output_tokens"] = sum(output_values)
    return usage


def decode_result(provider, result):
    if provider not in ("codex", "claude", "gemini"):
        raise UnsupportedCapability(f"CLI provider {provider!r} is not implemented")
    if result.returncode:
        diagnostic = (result.stderr + "\n" + result.stdout).lower()
        if any(marker in diagnostic for marker in (
            "unexpected argument", "unknown option", "unrecognized argument",
            "unknown feature", "unrecognized feature",
        )):
            raise UnsupportedCapability(
                f"{provider} CLI does not support required safety/transport flags; "
                "update the official CLI. Safety flags are never silently removed"
            )
        if provider == "codex":
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") in ("error", "turn.failed"):
                    message = json.dumps(event.get("error", event.get("message", ""))).lower()
                    if any(x in message for x in ("401 unauthorized", "authentication required", "not logged in")):
                        raise CLIAuthenticationError("Codex inference reported an authentication failure; use official CLI login")
        raise CLIError(f"{provider} CLI exited with status {result.returncode}; inspect the CLI locally")
    try:
        if provider == "codex":
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            if not events or any(not isinstance(e, dict) for e in events):
                raise ValueError
            if any(e.get("type") in ("error", "turn.failed") for e in events):
                raise CLIError("Codex reported a failed inference turn")
            if not any(e.get("type") == "turn.completed" for e in events):
                raise CLIProtocolError("Codex output is incomplete: no turn.completed event")
            if any(isinstance(e.get("item"), dict) and e["item"].get("type") in (
                "command_execution", "file_change", "mcp_tool_call", "web_search", "collab_tool_call",
            ) for e in events):
                raise CLIProtocolError("Provider executed a tool; only ARTEMIS may execute actions")
            answers = [e["item"]["text"] for e in events if e.get("type") == "item.completed"
                       and isinstance(e.get("item"), dict) and e["item"].get("type") == "agent_message"]
            if not answers:
                raise ValueError
            usage = next((e.get("usage", {}) for e in reversed(events)
                          if e.get("type") == "turn.completed"), {})
            return answers[-1], usage
        if provider == "claude":
            data = json.loads(result.stdout)
            if not isinstance(data, dict):
                raise ValueError
            if data.get("is_error") or data.get("type") != "result" or data.get("subtype") != "success":
                raise CLIError("Claude reported an unsuccessful inference result")
            # --json-schema returns a validated object under structured_output.
            structured = data.get("structured_output")
            answer = json.dumps(structured, ensure_ascii=False) if isinstance(structured, dict) else data["result"]
            if not isinstance(answer, str):
                raise ValueError
            return answer, data.get("usage", {})
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        if not events or any(not isinstance(e, dict) for e in events):
            raise ValueError
        if any(e.get("type") in ("tool_use", "tool_result") for e in events):
            raise CLIProtocolError("Gemini CLI executed a tool; only ARTEMIS may execute actions")
        if any(e.get("type") == "error" for e in events):
            raise CLIError("Gemini reported an inference error")
        final = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if final is None:
            raise CLIProtocolError("Gemini output is incomplete: no result event")
        if final.get("status") not in (None, "success"):
            raise CLIError("Gemini reported an unsuccessful inference result")
        statistics = final.get("stats", {})
        tools = statistics.get("tools", {}) if isinstance(statistics, dict) else {}
        if isinstance(tools, dict) and tools.get("totalCalls", 0):
            raise CLIProtocolError("Gemini used internal tools; only ARTEMIS may execute actions")
        response = final.get("response")
        if not isinstance(response, str):
            raise ValueError
        return response, _gemini_usage(statistics)
    except (ValueError, TypeError, KeyError):
        raise CLIProtocolError(f"Malformed {provider} CLI output") from None
