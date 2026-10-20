"""Antigravity host support is distinct from unsupported Pro inference."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from callisto.cli import app
from callisto.llm_adapter import discovery, providers
from callisto.llm_adapter.environment import cli_environment
from callisto.llm_adapter.errors import UnsupportedCapability
from callisto.settings import effective_settings
from callisto import setup, skill_install


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("CALLISTO_FORBID_LIVE_CLI", "1")
    monkeypatch.setenv("CALLISTO_CONFIG", str(tmp_path / "settings.json"))
    monkeypatch.delenv("CALLISTO_AI_CLI", raising=False)
    monkeypatch.delenv("CALLISTO_ANTIGRAVITY_EXECUTABLE", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))


def test_exact_provider_and_renamed_executable(monkeypatch):
    lookup = Mock(return_value="/official/agy")
    monkeypatch.setattr(discovery.shutil, "which", lookup)
    assert discovery.resolve_provider("antigravity") == "antigravity"
    assert discovery.discover_executable("antigravity") == "/official/agy"
    lookup.assert_called_once_with("agy")
    assert effective_settings(provider="antigravity").provider == "antigravity"


@pytest.mark.parametrize("platform", ["nt", "posix"])
def test_default_install_and_missing(monkeypatch, tmp_path, platform):
    monkeypatch.setattr(discovery, "os", SimpleNamespace(name=platform, environ=os.environ))
    monkeypatch.setattr(discovery.shutil, "which", lambda _: None)
    assert discovery.discover_executable("antigravity") is None
    relative = "agy/bin/agy.exe" if discovery.os.name == "nt" else ".local/bin/agy"
    binary = tmp_path / relative
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"MZ\x00\x00" if platform == "nt" else b"\x7fELF")
    assert discovery.discover_executable("antigravity") == str(binary)
    assert discovery.executable_command("antigravity") == [str(binary)]


def test_explicit_missing_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("CALLISTO_ANTIGRAVITY_EXECUTABLE", "/missing/agy")
    monkeypatch.setattr(discovery.shutil, "which", lambda _: None)
    assert discovery.discover_executable("antigravity") is None
    assert discovery.resolve_provider("antigravity") == "antigravity"


def test_no_shell_wrapper(monkeypatch, tmp_path):
    wrapper = tmp_path / "agy.cmd"
    wrapper.write_text("echo arbitrary")
    monkeypatch.setattr(discovery, "discover_executable", lambda _: str(wrapper))
    assert discovery.executable_command("antigravity") is None


def test_renamed_script_is_not_native(monkeypatch, tmp_path):
    wrapper = tmp_path / "agy.exe"
    wrapper.write_text("#!/bin/sh\necho arbitrary")
    monkeypatch.setattr(discovery, "discover_executable", lambda _: str(wrapper))
    assert discovery.executable_command("antigravity") is None


def test_skill_lifecycle_and_modified_preservation(tmp_path, monkeypatch):
    target = tmp_path / ".gemini/antigravity-cli/skills/callisto"
    assert skill_install.skill_directory(provider="antigravity") == target
    assert skill_install.install_skill(provider="antigravity")["current"]
    assert sorted(p.name for p in target.iterdir()) == ["SKILL.md", "callisto-install.json"]
    metadata = json.loads((target / "callisto-install.json").read_text())
    assert Path(metadata["python_executable"]).is_absolute()
    assert skill_install.install_skill(provider="antigravity")["current"]
    updated = tmp_path / "new-canonical.md"
    updated.write_text("---\nname: callisto\ndescription: Updated test skill\n---\n")
    monkeypatch.setattr(skill_install, "canonical_skill", lambda: updated)
    assert not skill_install.skill_status(provider="antigravity")["current"]
    assert skill_install.install_skill(provider="antigravity")["current"]
    assert (target / "SKILL.md").read_bytes() == updated.read_bytes()
    (target / "SKILL.md").write_text("user change")
    with pytest.raises(ValueError, match="preserved"):
        skill_install.install_skill(provider="antigravity")
    assert (target / "SKILL.md").read_text() == "user change"
    assert not (tmp_path / ".gemini/config/skills").exists()


@pytest.mark.parametrize("images", [[], ["unreadable-screen.png"]])
def test_inference_fails_before_launch_or_image_loss(monkeypatch, tmp_path, images):
    launcher = Mock(side_effect=AssertionError("must not launch"))
    monkeypatch.setattr(providers, "executable_command", launcher)
    with pytest.raises(UnsupportedCapability, match="UNSUPPORTED"):
        providers.command_for("antigravity", None, tmp_path, images, tmp_path / "schema.json")
    with pytest.raises(UnsupportedCapability):
        providers.build_stdin("antigravity", "request", images)
    with pytest.raises(UnsupportedCapability):
        providers.decode_result("antigravity", None)
    launcher.assert_not_called()


def test_setup_repairs_host_but_never_reports_pro_ready(monkeypatch):
    monkeypatch.setattr(setup, "available_providers", lambda: ["antigravity"])
    monkeypatch.setattr(setup, "dependencies_ready", lambda: True)
    monkeypatch.setattr(setup, "executable_command", lambda _: ["agy.exe"])
    monkeypatch.setattr(setup, "discover_executable", lambda _: "agy.exe")
    monkeypatch.setattr(setup, "adb_devices", lambda: ([], None))
    monkeypatch.setattr(setup, "helper_state", lambda *a, **kw: {
        "bundle": "absent", "provision": "not_attempted"})
    report = setup.setup_report(repair=True, check_login=False)
    assert report["status"] == "UNSUPPORTED"
    assert report["skills"]["antigravity"]["current"]
    assert report["cli"]["native_launcher"]
    assert report["cli"]["inference"] == "UNSUPPORTED"


def test_run_stops_before_android(monkeypatch, tmp_path):
    monkeypatch.delenv("CALLISTO_FORBID_LIVE_CLI")
    execute = Mock(side_effect=AssertionError("must not start Android"))
    monkeypatch.setattr("artemis.interfaces.cli.commands.run.execute_task", execute)
    result = CliRunner().invoke(app, ["run", "settings", "--ai-cli", "antigravity",
                                     "--traces-path", str(tmp_path / "traces")])
    assert result.exit_code == 2
    assert "UNSUPPORTED" in result.output
    assert not (tmp_path / "traces").exists()
    execute.assert_not_called()


def test_child_environment_removes_direct_api_overrides():
    source = {"GEMINI_API_KEY": "secret", "GOOGLE_GEMINI_BASE_URL": "override",
              "AGY_ADC_AUTH": "true", "USERPROFILE": "normal"}
    assert cli_environment("antigravity", source=source) == {"USERPROFILE": "normal"}
