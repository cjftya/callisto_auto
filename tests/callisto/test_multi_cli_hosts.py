"""Offline host-CLI routing and multimodal transport contracts.

No official AI CLI, Android device or paid inference is executed here.
"""
import base64
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from callisto.cli import app
from callisto.llm_adapter.discovery import resolve_provider
from callisto.llm_adapter.errors import CLIError, CLIProtocolError
from callisto.llm_adapter.process import ProcessResult
from callisto.llm_adapter.providers import build_stdin, command_for, decode_result
from callisto.settings import effective_settings, runtime_settings
from callisto.skill_install import skill_directory


SCHEMA = {"type": "object", "properties": {"content": {"type": "string"},
    "tool_calls": {"type": "array"}}, "required": ["content", "tool_calls"]}
ANSWER = {"content": "OK", "tool_calls": []}


@pytest.fixture(autouse=True)
def no_live_cli(monkeypatch, tmp_path):
    monkeypatch.delenv("CALLISTO_FORBID_LIVE_CLI", raising=False)
    monkeypatch.delenv("CALLISTO_AI_CLI", raising=False)
    monkeypatch.setenv("CALLISTO_CONFIG", str(tmp_path / "settings.json"))


def test_auto_provider_requires_unambiguous_host(monkeypatch):
    from callisto.llm_adapter import discovery
    monkeypatch.setattr(discovery, "discover_executable", lambda _: "/mock/cli")
    with pytest.raises(ValueError, match="--ai-cli"):
        resolve_provider()
    assert resolve_provider("gemini") == "gemini"
    with runtime_settings(provider="claude"):
        assert effective_settings().provider == "claude"
    assert effective_settings().provider == "auto"


@pytest.mark.parametrize("selected", ["codex", "claude", "gemini"])
def test_skill_host_scopes(selected, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    location = skill_directory(provider=selected)
    expected = {"codex": ".agents", "claude": ".claude", "gemini": ".gemini"}[selected]
    assert expected in location.parts and location.name == "callisto"


def test_codex_keeps_user_defaults_and_disables_provider_tools(monkeypatch, tmp_path):
    from callisto.llm_adapter import providers
    monkeypatch.setattr(providers, "executable_command", lambda _: ["/fake/codex"])
    command = command_for("codex", "IGNORED", tmp_path, ["screen.png"], tmp_path / "schema.json", "high")
    assert command[:2] == ["/fake/codex", "exec"]
    assert "--ignore-user-config" not in command
    assert "--model" not in command
    assert "model_reasoning_effort" not in " ".join(command)
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--image") + 1] == "screen.png"


def test_claude_vision_and_schema(monkeypatch, tmp_path):
    from callisto.llm_adapter import providers
    monkeypatch.setattr(providers, "executable_command", lambda _: ["/fake/claude"])
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(SCHEMA))
    picture = tmp_path / "screenshot.png"
    picture.write_bytes(b"PNG mock bytes")
    args = command_for("claude", None, tmp_path, [str(picture)], schema_file)
    assert args[:2] == ["/fake/claude", "-p"]
    assert "--input-format" in args and "stream-json" in args
    assert "--json-schema" in args and "--tools" in args
    assert args[args.index("--tools") + 1] == ""
    assert "--model" not in args
    payload = json.loads(build_stdin("claude", "Full history", [str(picture)]))
    assert payload["message"]["content"][0]["text"] == "Full history"
    image = payload["message"]["content"][1]["source"]
    assert image["media_type"] == "image/png"
    assert base64.b64decode(image["data"]) == picture.read_bytes()
    answer, usage = decode_result("claude", ProcessResult(0, json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "structured_output": ANSWER, "usage": {"input_tokens": 12, "output_tokens": 4}}), ""))
    assert json.loads(answer) == ANSWER and usage["input_tokens"] == 12


def test_claude_oversize_stdin_fails_closed(tmp_path):
    with pytest.raises(CLIProtocolError, match="size limit"):
        build_stdin("claude", "x" * 9_500_001, [])


def test_gemini_image_and_verified_completion(monkeypatch, tmp_path):
    from callisto.llm_adapter import providers
    monkeypatch.setattr(providers, "executable_command", lambda _: ["/fake/gemini"])
    args = command_for("gemini", None, tmp_path, ["screen.jpg"], tmp_path / "schema.json")
    assert args[:2] == ["/fake/gemini", "--prompt"]
    assert args[args.index("--approval-mode") + 1] == "plan"
    assert "--model" not in args
    assert "decision = \"deny\"" in (tmp_path / ".gemini/policies/callisto-deny.toml").read_text()
    image = tmp_path / "screen.jpg"
    image.write_bytes(b"mock screenshot")
    prompt = build_stdin("gemini", "History and schema", [str(image)])
    assert "History and schema" in prompt and "@"+image.as_posix() in prompt
    events = [{"type": "init"}, {"type": "result", "status": "success",
        "response": json.dumps(ANSWER),
        "stats": {"models": {"default": {"tokens": {"prompt": 13, "response": 3}}},
                  "tools": {"totalCalls": 0}}}]
    answer, usage = decode_result("gemini", ProcessResult(0, "\n".join(map(json.dumps, events)), ""))
    assert json.loads(answer) == ANSWER
    assert usage == {"input_tokens": 13, "output_tokens": 3}


@pytest.mark.parametrize("provider,payload", [
    ("gemini", [{"type": "tool_use"}, {"type": "result", "response": json.dumps(ANSWER)}]),
    ("gemini", [{"type": "result", "response": json.dumps(ANSWER), "stats": {"tools": {"totalCalls": 1}}}]),
    ("gemini", [{"type": "message", "content": "partial"}]),
])
def test_gemini_never_accepts_tool_effects_or_partial_result(provider, payload):
    with pytest.raises(CLIError):
        decode_result(provider, ProcessResult(0, "\n".join(map(json.dumps, payload)), ""))


@pytest.mark.parametrize("provider", ["codex", "claude", "gemini"])
def test_cli_run_selects_exact_host(monkeypatch, tmp_path, provider):
    monkeypatch.setattr("callisto.llm_adapter.discovery.discover_executable", lambda _: "/fake/bin")
    async def fake_execute(**kwargs):
        assert effective_settings().provider == provider
        kwargs["result_report"].update(status="completed", result={
            "content": {"test_summary": {"passed": 1}}})
    monkeypatch.setattr("artemis.interfaces.cli.commands.run.execute_task", fake_execute)
    result = CliRunner().invoke(app, ["run", "offline goal", "--ai-cli", provider,
                                      "--traces-path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["status"] == "completed"
