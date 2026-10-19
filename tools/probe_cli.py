"""P0 text gate: check real Codex inference without reading credentials.

This is a readiness probe, not the ARTEMIS adapter or a complete P0 pass.
Only sanitized status is emitted; raw CLI output stays in memory.
"""
import argparse
import json
import shutil
import subprocess
import tempfile


def classify(returncode, stdout, stderr):
    text = (stdout + "\n" + stderr).lower()
    if any(marker in text for marker in (
        "401 unauthorized", "could not parse your authentication token",
        "not logged in", "authentication required",
    )):
        return "authentication_failed"
    if returncode:
        return "cli_failed"
    completed = False
    answer = None
    try:
        for line in stdout.splitlines():
            event = json.loads(line)
            if event.get("type") in ("error", "turn.failed"):
                return "cli_failed"
            if event.get("type") == "turn.completed":
                completed = True
            item = event.get("item", {})
            if event.get("type") == "item.completed" and item.get("type") == "agent_message":
                answer = item.get("text", "").strip()
    except (ValueError, AttributeError, TypeError):
        return "invalid_output"
    return "passed" if completed and answer == "CALLISTO_OK" else "invalid_output"


def probe(executable="codex", timeout=45):
    path = shutil.which(executable)
    if path is None:
        return {"text": "not_installed", "p0_passed": False}
    with tempfile.TemporaryDirectory(prefix="callisto-probe-") as directory:
        command = [path, "exec", "--ignore-user-config", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only", "--json",
                   "-C", directory, "Return exactly CALLISTO_OK. Do not use tools."]
        try:
            result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, timeout=timeout, check=False)
            status = classify(result.returncode, result.stdout, result.stderr)
        except subprocess.TimeoutExpired as error:
            # subprocess.run kills and reaps the CLI on timeout. No raw logs persisted.
            def decode(value):
                return value.decode(errors="replace") if isinstance(value, bytes) else value or ""
            status = classify(1, decode(error.stdout), decode(error.stderr))
            if status != "authentication_failed":
                status = "timeout"
        except OSError:
            status = "launch_failed"
    return {"text": status, "p0_passed": False,
            "remaining": ["image", "json_schema", "tool_calls", "multi_turn", "cancellation"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex", help="Executable name or absolute path")
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    report = probe(args.codex, args.timeout)
    print(json.dumps(report, indent=2))
    return 0 if report["text"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
