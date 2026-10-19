"""Offline acceptance for v4.1; only fake Python subprocesses may run."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from typer.testing import CliRunner

from callisto.cli import app
from callisto.llm_adapter.environment import API_KEY_VARIABLES, PROVIDER_OVERRIDES, cli_environment
from callisto.llm_adapter.errors import UnsupportedCapability
from callisto.llm_adapter.process import ProcessResult, run_process
from callisto.llm_adapter.providers import command_for, decode_result
from callisto.skill_install import canonical_skill, install_skill, skill_status
from callisto.verdict import settle_report


def test_original_native_universal_and_action_engines_are_preserved():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/upstream-engine-manifest.json").read_text())
    assert len(manifest) >= 20
    for name, digest in manifest.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["codex", "claude"])
async def test_fake_child_uses_provider_auth_policy_without_changing_parent(provider, monkeypatch, tmp_path):
    blocked = API_KEY_VARIABLES | PROVIDER_OVERRIDES[provider]
    for key in blocked:
        monkeypatch.setenv(key, "test-only-do-not-forward")
    monkeypatch.setenv("OpenAi_Api_Key", "mixed-case-test-key")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "existing-login-location"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "existing-claude-location"))
    # Windows aliases differently cased names to the same variable. Compare
    # the prepared parent values, rather than assuming POSIX key identity.
    parent_values = {key: os.environ[key] for key in blocked | {"OpenAi_Api_Key"}}
    script = "import os,json; print(json.dumps({'keys':list(os.environ),'codex_home':os.environ.get('CODEX_HOME'),'claude_dir':os.environ.get('CLAUDE_CONFIG_DIR')}))"
    result = await run_process([sys.executable, "-c", script], stdin="", cwd=str(tmp_path), timeout=5, provider=provider)
    data = json.loads(result.stdout)
    assert not {key.upper() for key in data["keys"]} & blocked
    assert data["codex_home"] == str(tmp_path / "existing-login-location")
    assert data["claude_dir"] == str(tmp_path / "existing-claude-location")
    assert {key: os.environ[key] for key in parent_values} == parent_values


def test_auth_policies_are_separate_and_do_not_read_blocked_values():
    class Env(dict):
        def __getitem__(self, key):
            assert key != "OPENAI_API_KEY"
            return super().__getitem__(key)
    source = Env(OPENAI_API_KEY="not-read", PATH="existing", HOME="login-home", ANTHROPIC_BASE_URL="other-provider")
    assert cli_environment("codex", source=source) == {"PATH": "existing", "HOME": "login-home", "ANTHROPIC_BASE_URL": "other-provider"}
    assert "ANTHROPIC_BASE_URL" not in cli_environment("claude", source=source)


@pytest.mark.parametrize("summary", [None, [], "passed", {}, {"passed": 0}, {"passed": True}, {"passed": -1}, {"passed": "1"}, {"passed": 1, "unchecked": "0"}])
def test_missing_or_invalid_verdict_never_passes(summary):
    report = {"status": "completed", "result": {"content": {"test_summary": summary}}}
    settle_report(report)
    assert report["exit_code"] == 2 and report["test_status"] == "not_reported"


@pytest.mark.parametrize("cancel", [False, True])
def test_failed_or_cancelled_task_cannot_exit_success(monkeypatch, tmp_path, cancel):
    monkeypatch.delenv("CALLISTO_FORBID_LIVE_CLI")
    async def fake_task(**kwargs):
        kwargs["result_report"].update(status="completed", result={"content": {"test_summary": {"passed": 1}}})
        if cancel:
            raise asyncio.CancelledError
        raise RuntimeError("private diagnostic")
    monkeypatch.setattr("artemis.interfaces.cli.commands.run.execute_task", fake_task)
    result = CliRunner().invoke(app, ["run", "mock only", "--traces-path", str(tmp_path)])
    metadata = json.loads(result.stdout)
    report = json.loads(Path(metadata["result_file"]).read_text())
    assert result.exit_code == metadata["exit_code"] == report["exit_code"] == (130 if cancel else 1)
    assert "private diagnostic" not in json.dumps(report)


def test_install_update_and_detect_modified_skill_outside_project(tmp_path, monkeypatch):
    parent = tmp_path / "user-skills"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert not skill_status(parent)["installed"]
    assert install_skill(parent)["current"]
    assert (parent / "callisto/SKILL.md").read_bytes() == canonical_skill().read_bytes()
    assert install_skill(parent)["current"]
    skill = parent / "callisto/SKILL.md"
    skill.write_text("user-modified", encoding="utf-8")
    assert not skill_status(parent)["managed"]
    with pytest.raises(ValueError, match="preserved"):
        install_skill(parent)
    assert skill.read_text() == "user-modified"


def test_standard_skill_scope_uses_home_agents_skills(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    report = install_skill()
    assert Path(report["path"]) == tmp_path / ".agents/skills/callisto"
    assert report["host_recognition"] == "not_checked"
    assert CliRunner().invoke(app, ["skill", "status"]).exit_code == 0


@pytest.mark.parametrize("diagnostic", ["unexpected argument --ignore-user-config", "unknown feature plugins", "unknown option --json"])
def test_old_cli_options_fail_without_unsafe_retries(diagnostic):
    with pytest.raises(UnsupportedCapability, match="update the official CLI") as error:
        decode_result("codex", ProcessResult(2, "", diagnostic + " private-value"))
    assert "private-value" not in str(error.value)


def test_windows_cmd_is_rejected_without_running_shell(monkeypatch, tmp_path):
    from callisto.llm_adapter import providers
    monkeypatch.delenv("CALLISTO_FORBID_LIVE_CLI")
    monkeypatch.setattr(providers, "os", SimpleNamespace(name="nt", environ=os.environ))
    monkeypatch.setattr(providers.shutil, "which", lambda _: r"C:\Program Files\Codex\codex.cmd")
    with pytest.raises(UnsupportedCapability, match="official native .exe"):
        command_for("codex", None, tmp_path, [], tmp_path / "schema.json")


def test_external_helper_bundle_integrity_and_offline_status(monkeypatch, tmp_path):
    from artemis.runtime.helper_manager import load_bundled_helper, helper_artifact_paths
    monkeypatch.setenv("CALLISTO_HELPER_DIR", str(tmp_path))
    apk, manifest = helper_artifact_paths()
    assert load_bundled_helper() is None
    assert CliRunner().invoke(app, ["helper", "bundle-status"]).exit_code == 1
    apk.write_bytes(b"fake apk fixture")
    manifest.write_text(json.dumps({"package": "com.artemis.helper", "version_code": 6,
        "version_name": "1.2.0", "sha256": hashlib.sha256(apk.read_bytes()).hexdigest()}))
    assert load_bundled_helper().version_code == 6
    assert CliRunner().invoke(app, ["helper", "bundle-status"]).exit_code == 0
    apk.write_bytes(b"corrupted")
    assert load_bundled_helper() is None


@pytest.mark.asyncio
async def test_native_explorer_can_use_cli_port_without_gemini_model_label(monkeypatch, tmp_path):
    from artemis.agents.explorer.explorer import Explorer
    from artemis.agents.explorer.tiers import get_tier
    from callisto.llm_adapter.native import Client
    monkeypatch.setenv("CALLISTO_EXPLORER_ENGINE", "native")
    ctx = SimpleNamespace(llm_config=SimpleNamespace(explorer=SimpleNamespace(model="gpt-6.1-sol")), agent_config=None, data_engine=None)
    explorer = Explorer(ctx)
    assert explorer.use_native_gemini
    tier = get_tier("pro")
    explorer._apply_tier(tier)
    monkeypatch.setattr(explorer, "_init_image_pool", lambda _: None)
    monkeypatch.setattr(explorer, "_build_prompt_template", lambda _: ("original native prompt", None))
    monkeypatch.setattr(explorer, "_prepare_initial_annotation", lambda *a: ("", str(tmp_path / "screen.jpg")))
    monkeypatch.setattr(explorer, "_resolve_model_params", lambda: ("gpt-6.1-sol", None, None, None))
    native = AsyncMock(return_value='{"candidates":[],"fallback_message":"fixture"}')
    monkeypatch.setattr(explorer, "_run_native", native)
    await explorer._run_loop(tier, "find", "", "screen.jpg", None, "", None, [])
    assert isinstance(native.call_args.kwargs["client"], Client)
    assert native.call_args.kwargs["enable_caching"] is False
    with pytest.raises(UnsupportedCapability, match="Context Cache"):
        await explorer._run_loop(tier, "find", "", "screen.jpg", None, "", True, [])


@pytest.mark.asyncio
async def test_original_native_loop_reaches_cli_json_and_validates_submit(monkeypatch, tmp_path):
    from artemis.agents.explorer.explorer import Explorer
    from artemis.agents.explorer.tiers import get_tier
    from callisto.llm_adapter import model
    from callisto.llm_adapter.native import Client
    monkeypatch.setenv("CALLISTO_EXPLORER_ENGINE", "native")
    monkeypatch.setenv("ARTEMIS_USE_FILE_API", "false")
    ctx = SimpleNamespace(llm_config=SimpleNamespace(explorer=SimpleNamespace(model="gpt-6.1-sol")), agent_config=None, data_engine=None)
    explorer = Explorer(ctx)
    explorer._apply_tier(get_tier("pro"))
    image = tmp_path / "screen.jpg"
    image.write_bytes(b"fake screenshot bytes")
    answer = {"candidates": [], "fallback_message": "No matching button in fixture"}
    text = json.dumps({"content": "", "tool_calls": [{"id": "native-submit", "name": "submit_answer", "args_json": json.dumps(answer)}]})
    result = ProcessResult(0, '\n'.join(map(json.dumps, [
        {"type": "item.completed", "item": {"type": "agent_message", "text": text}},
        {"type": "turn.completed"}])), "")
    monkeypatch.setattr(model, "command_for", lambda *args: ["FAKE_NOT_EXECUTED"])
    process = AsyncMock(return_value=result)
    monkeypatch.setattr(model, "run_process", process)
    value = await explorer._run_native(client=Client(), query="find a button", context_feedback="", minimal_list="",
        img_to_read=str(image), enable_caching=False, prompt_template="original prompt", model_name="gpt-6.1-sol",
        temperature=None, thinking_level=None, max_turns=3)
    assert json.loads(value) == answer
    assert process.await_count == 1
    assert process.call_args.kwargs["provider"] == "codex"
