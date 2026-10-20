"""Setup/configuration contracts using isolated homes and mocked device/CLI probes."""
import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from callisto.cli import app
from callisto.settings import effective_settings, runtime_settings, save_settings
from callisto import setup


@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("CALLISTO_CONFIG", str(tmp_path / "settings.json"))
    for name in ("CALLISTO_AI_CLI", "CALLISTO_MODEL", "CALLISTO_REASONING_EFFORT", "CALLISTO_IMAGE_POLICY", "CALLISTO_DEVICE_SERIAL", "CALLISTO_CODEX_EXECUTABLE"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path / "settings.json"


def test_precedence_idempotence_and_no_environment_mutation(isolated_settings, monkeypatch):
    assert save_settings(image_policy="quality")
    before = isolated_settings.stat().st_mtime_ns
    assert not save_settings()
    assert isolated_settings.stat().st_mtime_ns == before
    monkeypatch.setenv("CALLISTO_IMAGE_POLICY", "economy")
    with runtime_settings(image_policy="balanced"):
        assert effective_settings().image_policy == "balanced"
    assert effective_settings().image_policy == "economy"
    assert effective_settings(image_policy="off").image_policy == "off"
    with pytest.raises(ValueError):
        save_settings(api_key="do not store this")
    assert "api_key" not in isolated_settings.read_text()


def test_malformed_settings_are_preserved(isolated_settings):
    isolated_settings.write_text("corrupt")
    result = CliRunner().invoke(app,["setup","repair","--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["status"] == "ACTION_REQUIRED"
    assert isolated_settings.read_text() == "corrupt"


@pytest.fixture
def prepared(isolated_settings, monkeypatch):
    monkeypatch.setattr(setup,"available_providers",lambda: ["codex"])
    monkeypatch.setattr(setup,"resolve_provider",lambda *_:"codex")
    monkeypatch.setattr(setup,"executable_command",lambda _: ["/native/codex.exe"])
    monkeypatch.setattr(setup,"login_state",lambda *_:"authenticated")
    monkeypatch.setattr(setup,"dependencies_ready",lambda:True)
    monkeypatch.setattr(setup,"skill_status",lambda **kwargs:{"installed":True,"managed":True,"current":True})
    monkeypatch.setattr(setup,"helper_state",lambda *args,**kwargs:{"bundle":"absent","backend":"uiautomator2_fallback","protocol":"not_checked","provision":"not_attempted"})
    monkeypatch.setattr(setup,"adb_devices",lambda:([{"serial":"one","state":"device"}],None))
    return isolated_settings


def test_check_is_read_only_and_reports_honest_fallback(prepared):
    result = CliRunner().invoke(app,["setup","check","--json"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["device_serial"] == "one" and report["status"] == "READY"
    assert report["helper"]["backend"] == "uiautomator2_fallback"
    assert not prepared.exists()


def test_repair_is_idempotent_and_preserves_modified_skill(prepared, monkeypatch):
    first = setup.setup_report(repair=True)
    assert first["changes"] == ["settings"]
    assert json.loads(prepared.read_text())["device_serial"] is None
    assert not setup.setup_report(repair=True)["changes"]
    installer = Mock()
    monkeypatch.setattr(setup,"install_skill",installer)
    monkeypatch.setattr(setup,"skill_status",lambda **kwargs:{"installed":True,"managed":False,"current":False})
    assert setup.setup_report(repair=True)["status"] == "ACTION_REQUIRED"
    installer.assert_not_called()


@pytest.mark.parametrize("devices", [[],[{"serial":"one","state":"unauthorized"}], [{"serial":"one","state":"offline"}], [{"serial":"a","state":"device"},{"serial":"b","state":"device"}]])
def test_absent_unapproved_offline_multiple_devices_never_guess(prepared, monkeypatch, devices):
    monkeypatch.setattr(setup,"adb_devices",lambda:(devices,None))
    report = setup.setup_report(repair=True)
    assert report["device_serial"] is None and report["status"] == "ACTION_REQUIRED"
    if len(devices) == 2:
        assert setup.setup_report(device="b")["device_serial"] == "b"


def test_adb_devices_decodes_utf8_and_invalid_bytes(monkeypatch):
    from artemis.runtime import adb_endpoint

    # Exercise the real subprocess decoder, including stderr, without launching ADB.
    output = "List of devices attached\n연결\none\tdevice\ntwo\tunauthorized\nthree\toffline\nfour\tno permissions\n".encode() + b"\xff\n"
    with pytest.raises(UnicodeDecodeError):
        output.decode("cp949")
    command = [sys.executable, "-c", f"import os; os.write(1, {output!r}); os.write(2, b'\\xff')"]
    monkeypatch.setattr(adb_endpoint, "adb_command", lambda args: command)
    assert setup.adb_devices() == ([
        {"serial": "one", "state": "device"},
        {"serial": "two", "state": "unauthorized"},
        {"serial": "three", "state": "offline"},
        {"serial": "four", "state": "no"},
    ], None)


@pytest.mark.parametrize("failure, expected", [
    (FileNotFoundError("adb"), "adb_unavailable"),
    (PermissionError("adb"), "adb_failed"),
    (OSError("invalid executable"), "adb_failed"),
    (subprocess.TimeoutExpired("adb", 15), "adb_timeout"),
    (None, "adb_failed"),
])
def test_adb_devices_classifies_failures(monkeypatch, failure, expected):
    from artemis.runtime import adb_endpoint

    monkeypatch.setattr(adb_endpoint, "adb_command", lambda args: ["adb", *args])
    run = Mock(side_effect=failure, return_value=SimpleNamespace(returncode=1))
    monkeypatch.setattr(setup.subprocess, "run", run)
    assert setup.adb_devices() == ([], expected)


def test_adb_devices_missing_during_path_resolution(monkeypatch):
    from artemis.runtime import adb_endpoint

    monkeypatch.setattr(adb_endpoint, "adb_command", Mock(side_effect=FileNotFoundError("adb")))
    run = Mock(side_effect=AssertionError("must not launch missing adb"))
    monkeypatch.setattr(setup.subprocess, "run", run)
    assert setup.adb_devices() == ([], "adb_unavailable")
    run.assert_not_called()


@pytest.mark.parametrize("command", [[], ["check"], ["repair"]])
@pytest.mark.parametrize("devices, error, message", [
    ([], "adb_unavailable", "Install Android platform-tools"),
    ([], "adb_failed", "ADB device discovery failed"),
    ([], "adb_timeout", "ADB device discovery timed out"),
    ([], None, "No Android devices found"),
    ([{"serial": "one", "state": "unauthorized"}], None, "Authorize USB debugging"),
    ([{"serial": "one", "state": "offline"}], None, "Android device is offline"),
])
def test_setup_adb_guidance_matches_cause(prepared, monkeypatch, command, devices, error, message):
    monkeypatch.setattr(setup, "adb_devices", lambda: (devices, error))
    result = CliRunner().invoke(app, ["setup", *command, "--json"])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["status"] == "ACTION_REQUIRED"
    assert report["devices"] == devices and report["device_serial"] is None
    assert report["next_action"].startswith(message)
    assert report["issues"] == [report["next_action"]]
    assert report["helper"]["backend"] == "uiautomator2_fallback"
    assert prepared.exists() == (command != ["check"])


def test_selected_device_guidance_ignores_other_devices(prepared, monkeypatch):
    devices = [{"serial": "one", "state": "unauthorized"}, {"serial": "two", "state": "offline"}]
    monkeypatch.setattr(setup, "adb_devices", lambda: (devices, None))
    assert setup.setup_report(device="two")["next_action"].startswith("Android device is offline")


def test_invalid_helper_is_action_required(prepared, monkeypatch):
    monkeypatch.setattr(setup,"helper_state",lambda *args,**kwargs:{"bundle":"invalid","protocol":"not_checked","provision":"not_attempted"})
    assert setup.setup_report()["status"] == "ACTION_REQUIRED"


def test_provider_support_and_no_live_probe_offline(isolated_settings, monkeypatch):
    launch = Mock(side_effect=AssertionError("must not launch official CLI"))
    monkeypatch.setattr(setup.subprocess,"run",launch)
    assert setup.login_state("codex","/native/codex.exe") == "not_checked_offline"
    launch.assert_not_called()
    monkeypatch.setattr(setup,"dependencies_ready",lambda:True)
    monkeypatch.setattr(setup,"adb_devices",lambda:([],None))
    monkeypatch.setenv("CALLISTO_AI_CLI","gemini")
    report = setup.setup_report(ai_cli="gemini")
    assert report["status"] == "ACTION_REQUIRED"
    assert report["provider"] == "gemini"


def test_cli_owns_model_selection_even_with_legacy_hints(isolated_settings, monkeypatch):
    from callisto.llm_adapter.model import configured_model
    save_settings(image_policy="economy")
    monkeypatch.setenv("CALLISTO_AI_CLI", "codex")
    monkeypatch.setenv("CALLISTO_MODEL", "old-fixed-model")
    monkeypatch.setenv("CALLISTO_REASONING_EFFORT", "high")
    with runtime_settings(image_policy="quality"):
        model = configured_model(model="legacy", reasoning_effort="high")
        assert model.model_name is None and model.reasoning_effort is None
        assert model.image_policy == "quality"
    assert configured_model().model_name is None


def test_old_settings_strip_model_fields(isolated_settings):
    isolated_settings.write_text(json.dumps({"provider": "codex", "model": "old",
        "reasoning": "medium", "image_policy": "balanced"}), encoding="utf-8")
    assert effective_settings().image_policy == "balanced"
    assert save_settings()
    persisted = json.loads(isolated_settings.read_text(encoding="utf-8"))
    assert "model" not in persisted and "reasoning" not in persisted


def test_run_help_has_no_model_overrides():
    result = CliRunner().invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "--model" not in result.output and "--reasoning" not in result.output


def test_native_npm_discovery_matches_architecture_and_respects_explicit_path(isolated_settings, tmp_path, monkeypatch):
    from callisto.llm_adapter import discovery
    root = tmp_path / "npm"
    root.mkdir()
    shim = root / "codex.cmd"
    shim.touch()
    native = root / "node_modules/@openai/codex/vendor/x86_64-pc-windows-msvc/codex/codex.exe"
    native.parent.mkdir(parents=True)
    native.touch()
    other = root / "node_modules/@openai/codex/vendor/aarch64-pc-windows-msvc/codex/codex.exe"
    other.parent.mkdir(parents=True)
    other.touch()
    monkeypatch.setattr(discovery,"os",SimpleNamespace(name="nt",environ={}))
    monkeypatch.setattr(discovery.platform,"machine",lambda:"AMD64")
    monkeypatch.setattr(discovery.shutil,"which",lambda _:str(shim))
    assert discovery.discover_executable("codex")==str(native)
    save_settings(codex_executable=str(shim))
    assert discovery.discover_executable("codex")==str(shim)


def test_helper_protocol_unknown_never_provisions(isolated_settings, monkeypatch, tmp_path):
    # Import the module explicitly; runtime may export the manager instance.
    import importlib
    module=importlib.import_module("artemis.runtime.helper_manager")
    apk=tmp_path/"helper.apk"
    manifest=tmp_path/"helper_manifest.json"
    apk.touch()
    manifest.write_text(json.dumps({"protocol_version":1}))
    manager=SimpleNamespace(provision=Mock(side_effect=AssertionError("unverified install")),status=Mock(return_value={}))
    monkeypatch.setattr(module,"helper_artifact_paths",lambda:(apk,manifest))
    monkeypatch.setattr(module,"load_bundled_helper",lambda:object())
    monkeypatch.setattr(module,"helper_manager",manager)
    assert setup.helper_state("one",repair=True)["bundle"]=="protocol_unverified"
    manager.provision.assert_not_called()
