"""Offline multi-CLI registration: no provider subprocesses or Android inference."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from callisto import setup
from callisto.cli import app
from callisto import skill_install


@pytest.fixture
def auto_setup(monkeypatch, tmp_path):
    monkeypatch.setenv("CALLISTO_CONFIG", str(tmp_path / "callisto.json"))
    monkeypatch.delenv("CALLISTO_AI_CLI", raising=False)
    monkeypatch.setattr(setup, "available_providers", lambda: ["codex", "claude", "gemini"])
    monkeypatch.setattr(setup, "executable_command", lambda name: [f"/fake/{name}"])
    monkeypatch.setattr(setup, "login_state", lambda *args: "not_checked_offline")
    monkeypatch.setattr(setup, "dependencies_ready", lambda: True)
    monkeypatch.setattr(setup, "adb_devices", lambda: ([{"serial": "one", "state": "device"}], None))
    monkeypatch.setattr(setup, "helper_state", lambda *args, **kwargs: {
        "bundle": "absent", "backend": "uiautomator2_fallback",
        "protocol": "not_checked", "provision": "not_attempted"})
    return tmp_path


def test_setup_auto_repairs_every_host_without_a_choice(auto_setup, monkeypatch):
    seen = []
    monkeypatch.setattr(setup, "skill_status", lambda **kwargs: {
        "installed": False, "managed": False, "current": False})
    def install(*, provider):
        seen.append(provider)
        return {"installed": True, "managed": True, "current": True}
    monkeypatch.setattr(setup, "install_skill", install)
    report = setup.setup_report(repair=True)
    assert report["status"] == "READY"
    assert report["provider"] == "auto"
    assert report["providers"] == ["codex", "claude", "gemini"]
    assert seen == ["codex", "claude", "gemini"]
    assert all(value["current"] for value in report["skills"].values())
    assert report["changes"][:3] == ["skill:codex", "skill:claude", "skill:gemini"]
    assert "provider" not in json.loads((auto_setup / "callisto.json").read_text())


def test_setup_check_is_read_only_across_multiple_hosts(auto_setup, monkeypatch):
    installer = Mock(side_effect=AssertionError("check must not install a Skill"))
    monkeypatch.setattr(setup, "install_skill", installer)
    monkeypatch.setattr(setup, "skill_status", lambda **kwargs: {
        "installed": True, "managed": True, "current": True})
    result = CliRunner().invoke(app, ["setup", "check", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert sorted(report["skills"]) == ["claude", "codex", "gemini"]
    assert not report["changes"]
    assert not (auto_setup / "callisto.json").exists()
    installer.assert_not_called()


def test_modified_skill_does_not_block_other_hosts(auto_setup, monkeypatch):
    monkeypatch.setattr(setup, "available_providers", lambda: ["codex", "claude"])
    monkeypatch.setattr(setup, "skill_status", lambda *, provider: (
        {"installed": True, "managed": False, "current": False}
        if provider == "codex" else
        {"installed": False, "managed": False, "current": False}))
    called = []
    def install(*, provider):
        called.append(provider)
        return {"installed": True, "managed": True, "current": True}
    monkeypatch.setattr(setup, "install_skill", install)
    report = setup.setup_report(repair=True)
    assert called == ["claude"]
    assert report["status"] == "ACTION_REQUIRED"
    assert report["skills"]["codex"]["current"] is False
    assert report["skills"]["claude"]["current"] is True
    assert "skill:claude" in report["changes"]


def test_explicit_host_is_still_single_host(auto_setup, monkeypatch):
    monkeypatch.setattr(setup, "skill_status", lambda **kwargs: {
        "installed": True, "managed": True, "current": True})
    report = setup.setup_report(ai_cli="claude")
    assert report["status"] == "READY"
    assert report["provider"] == "claude"
    assert report["providers"] == ["claude"]
    assert list(report["skills"]) == ["claude"]
    assert report["skill"]["current"]


def test_setup_reports_when_no_usable_cli(auto_setup, monkeypatch):
    monkeypatch.setattr(setup, "available_providers", lambda: [])
    result = setup.setup_report()
    assert result["status"] == "ACTION_REQUIRED"
    assert result["providers"] == []
    assert any("No usable AI CLI" in issue for issue in result["issues"])


def test_skill_commands_register_every_host_and_preserve_modified_one(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(skill_install, "available_providers",
                        lambda: ["codex", "claude", "gemini"])
    runner = CliRunner()
    result = runner.invoke(app, ["skill", "install"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["current"] and len(report["hosts"]) == 3
    for host in ("codex", "claude", "gemini"):
        assert Path(skill_install.skill_directory(provider=host), "SKILL.md").is_file()

    skill = skill_install.skill_directory(provider="claude") / "SKILL.md"
    skill.write_text("user-edit", encoding="utf-8")
    changed = runner.invoke(app, ["skill", "update"])
    assert changed.exit_code == 1, changed.output
    status = json.loads(changed.stdout)
    assert status["hosts"]["claude"]["current"] is False
    assert status["hosts"]["codex"]["current"]
    assert status["hosts"]["gemini"]["current"]
    assert skill.read_text() == "user-edit"
    assert runner.invoke(app, ["skill", "status"]).exit_code == 1


def test_skill_auto_custom_directory_requires_host_for_multiple_clis(monkeypatch, tmp_path):
    monkeypatch.setattr(skill_install, "available_providers", lambda: ["codex", "gemini"])
    result = CliRunner().invoke(app, ["skill", "install", "--directory", str(tmp_path)])
    assert result.exit_code != 0
    assert not (tmp_path / "callisto").exists()
