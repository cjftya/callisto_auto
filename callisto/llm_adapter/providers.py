"""Official headless CLI formats, separate from agent response schemas.

Codex is the initial image-capable implementation. Claude text is experimental.
No provider is considered live-validated by mocked tests.
"""

import json
import os
import shutil

from callisto.llm_adapter.errors import CLIAuthenticationError, CLIError, CLIProtocolError, UnsupportedCapability


def command_for(provider, model, directory, images, schema_path, reasoning_effort=None):
    if os.environ.get("CALLISTO_FORBID_LIVE_CLI") == "1":
        raise CLIError("Live AI CLI execution is forbidden in this environment")
    if provider not in ("codex", "claude"):
        raise UnsupportedCapability(f"CLI provider {provider!r} is not implemented")
    executable = os.environ.get(f"CALLISTO_{provider.upper()}_EXECUTABLE", provider)
    path = shutil.which(executable)
    if not path:
        raise CLIError(f"Install and log in to {provider} CLI on the machine running Callisto")
    if provider == "codex":
        command = [path, "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                   "--disable", "shell_tool", "--disable", "apps", "--disable", "plugins",
                   "--disable", "hooks", "--disable", "multi_agent", "-c", 'web_search="disabled"',
                   "--json", "--output-schema", str(schema_path), "-C", str(directory)]
        if model:
            command += ["--model", model]
        if reasoning_effort:
            command += ["-c", f'model_reasoning_effort="{reasoning_effort}"']
        for path in images:
            command += ["--image", path]
        return [*command, "-"]
    if images:
        raise UnsupportedCapability("Claude CLI image attachment transport is not implemented; use Codex")
    command = [path, "-p", "--output-format", "json", "--tools", "", "--strict-mcp-config",
               "--mcp-config", '{"mcpServers":{}}', "--no-session-persistence"]
    if model:
        command += ["--model", model]
    return command


def decode_result(provider, result):
    if provider not in ("codex", "claude"):
        raise UnsupportedCapability(f"CLI provider {provider!r} is not implemented")
    if result.returncode:
        # Do not classify unrelated plugin stderr warnings as model auth failures.
        # Exit failures remain explicit; stderr never escapes into traces/errors.
        if provider == "codex":
            for line in result.stdout.splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") in ("error", "turn.failed"):
                    error = event.get("error", event.get("message", ""))
                    message = json.dumps(error).lower()
                    if any(marker in message for marker in ("401 unauthorized", "authentication required", "not logged in")):
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
            usage = next((e.get("usage", {}) for e in reversed(events) if e.get("type") == "turn.completed"), {})
            return answers[-1], usage
        data = json.loads(result.stdout)
        if not isinstance(data, dict):
            raise ValueError
        if data.get("is_error") or data.get("type") != "result" or data.get("subtype") != "success":
            raise CLIError("Claude reported an unsuccessful inference result")
        return data["result"], data.get("usage", {})
    except (ValueError, TypeError, KeyError):
        raise CLIProtocolError(f"Malformed {provider} CLI output") from None
