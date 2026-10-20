"""Idempotent local preparation. Never runs model inference or navigates Android."""
import json
import os
import platform
import subprocess
import sys
from typing import Annotated

import typer

from callisto.llm_adapter.discovery import discover_executable
from callisto.llm_adapter.environment import cli_environment
from callisto.settings import effective_settings, save_settings, settings_path
from callisto.skill_install import install_skill, skill_status

setup_app = typer.Typer(invoke_without_command=True, help="Prepare local settings, Skill and verified Helper; never run inference.")


def login_state(provider, executable):
    if os.environ.get("CALLISTO_FORBID_LIVE_CLI") == "1":
        return "not_checked_offline"
    if provider != "codex":
        return "unsupported_probe"
    try:
        result = subprocess.run([executable, "login", "status"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
            env=cli_environment(provider), check=False)
        return "authenticated" if result.returncode == 0 else "login_required"
    except (OSError, subprocess.TimeoutExpired):
        return "probe_failed"


def adb_devices():
    from artemis.runtime.adb_endpoint import adb_command
    try:
        result = subprocess.run(adb_command(["devices"]), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=15, check=False)
        if result.returncode != 0:
            return [], "adb_failed"
        devices = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] in ("device", "unauthorized", "offline", "no"):
                devices.append({"serial": parts[0], "state": parts[1]})
        return devices, None
    except (OSError, subprocess.TimeoutExpired):
        return [], "adb_unavailable"


def helper_state(serial, repair=False):
    from artemis.runtime.helper_manager import helper_artifact_paths, helper_manager, load_bundled_helper, MIN_PROTOCOL_VERSION
    apk, manifest = helper_artifact_paths()
    bundle = load_bundled_helper()
    result = {"bundle": "verified" if bundle else "invalid" if apk.exists() else "absent",
              "backend": "uiautomator2_fallback",
              "protocol": "not_checked", "provision": "not_attempted"}
    if bundle:
        declared = json.loads(manifest.read_text(encoding="utf-8")).get("protocol_version")
        if type(declared) is not int or declared < MIN_PROTOCOL_VERSION:
            result["bundle"] = "protocol_unverified"
    if serial:
        if repair and result["bundle"] == "verified":
            # Setup is explicitly authorized to provision only this selected device.
            # Use the same execution lock as tasks to avoid racing active automation.
            from artemis.runtime.device_lock import DeviceExecutionLock
            from artemis.runtime.adb_endpoint import current_adb_endpoint
            lock = DeviceExecutionLock(serial, description="Callisto setup", lock_scope=current_adb_endpoint().identity)
            lock.acquire(blocking=False)
            try:
                provision = helper_manager.provision(serial)
            finally:
                lock.release()
            result["provision"] = "ready" if provision.ok else "action_required"
        status = helper_manager.status(serial)
        result["protocol"] = "supported" if status.get("protocol_supported") else "not_ready"
        result["installed"] = status.get("installed", False)
        result["enabled"] = status.get("enabled", False)
        if status.get("protocol_supported") and status.get("enabled"):
            result["backend"] = "helper"
    return result


def dependencies_ready():
    try:
        return subprocess.run([sys.executable, "-m", "pip", "check"], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def setup_report(*, repair=False, device=None, check_login=True, interactive=False):
    issues = []
    report = {"status": "ACTION_REQUIRED", "os": platform.system(), "architecture": platform.machine(),
              "python": platform.python_version(), "profile": "pro", "live_inference": "not_run",
              "config_file": str(settings_path()), "changes": []}
    try:
        settings = effective_settings()
    except ValueError:
        report.update(issues=["Invalid user configuration; fix the settings file before retrying."], next_action="Inspect the Callisto user settings file.")
        return report
    report.update(provider=settings.provider, image_policy=settings.image_policy)
    report["dependencies_ready"] = dependencies_ready()
    if not report["dependencies_ready"]:
        issues.append("Rerun setup.ps1 or setup.sh to repair the Python package environment.")
    if settings.provider != "codex":
        report.update(status="UNSUPPORTED", issues=["Claude is experimental text-only; Gemini is not implemented for Android image inference."], next_action="Select Codex for Android tests.")
        return report
    executable = discover_executable(settings.provider)
    supported = bool(executable and (os.name != "nt" or executable.lower().endswith(".exe")))
    report["cli"] = {"installed": bool(executable), "native_launcher": supported}
    if not supported:
        issues.append("Install official Codex native binary; set CALLISTO_CODEX_EXECUTABLE to its .exe on Windows.")
    report["authentication"] = login_state(settings.provider, executable) if supported and check_login else "not_checked"
    if report["authentication"] != "authenticated":
        issues.append("Use official Codex login, then rerun callisto setup check on the execution PC.")
    try:
        skill = skill_status()
        if repair and (not skill["installed"] or skill["managed"]) and not skill["current"]:
            skill = install_skill()
            report["changes"].append("skill")
        report["skill"] = {k: skill[k] for k in ("installed", "managed", "current")}
        if not skill["current"]:
            issues.append("Run callisto setup repair; move a modified/unmanaged Skill yourself if it blocks installation.")
    except (OSError, ValueError, RuntimeError):
        issues.append("Skill preparation failed; existing user files were preserved.")
    devices, error = adb_devices()
    report["devices"] = devices
    ready = [d["serial"] for d in devices if d["state"] == "device"]
    selected = device or settings.device_serial
    explicitly_selected = bool(selected)
    if not selected and len(ready) == 1:
        selected = ready[0]
    if not selected and len(ready) > 1 and interactive:
        for i, serial in enumerate(ready, 1):
            typer.echo(f"{i}: {serial}")
        selected = ready[typer.prompt("Select device number", type=typer.IntRange(1, len(ready))) - 1]
        explicitly_selected = True
    if error:
        issues.append("Install Android platform-tools and ensure adb is available, then reconnect USB.")
    elif selected not in ready:
        issues.append("Connect and authorize USB debugging; with multiple devices pass --device-serial explicitly.")
    report["device_serial"] = selected if selected in ready else None
    if repair:
        updates = {"device_serial": selected} if selected in ready and explicitly_selected else {}
        if supported and not settings.codex_executable:
            updates["codex_executable"] = executable
        if save_settings(**updates):
            report["changes"].append("settings")
    try:
        helper = helper_state(report["device_serial"], repair=repair)
        report["helper"] = helper
        if helper["bundle"] in ("invalid", "protocol_unverified"):
            issues.append("Helper APK/manifest/protocol is not verified; installation refused. Supply a verified bundle.")
        if helper["provision"] == "action_required" or (helper["bundle"] == "verified" and helper["protocol"] != "supported"):
            issues.append("Run callisto setup repair and enable the Helper in Android Accessibility settings if requested.")
    except Exception as error:
        # Helper/ADB diagnostics can contain screen data. Expose only failure type.
        report["helper"] = {"backend": "uiautomator2_fallback", "error_type": type(error).__name__}
        issues.append("Helper check failed; inspect callisto helper status on the execution PC.")
    report.update(status="ACTION_REQUIRED" if issues else "READY", issues=issues,
                  next_action=issues[0] if issues else "Ask Codex to test Android with Callisto.")
    return report


def _execute(repair, device, skip_login, as_json, interactive=False):
    try:
        report = setup_report(repair=repair, device=device, check_login=not skip_login, interactive=interactive)
    except (OSError, ValueError):
        report = {"status": "ACTION_REQUIRED", "next_action": "Resolve local settings/file permissions and rerun callisto setup repair."}
    typer.echo(json.dumps(report, indent=2) if as_json else report["status"] + "\n" + report["next_action"] + "\n" + json.dumps(report, indent=2))
    raise typer.Exit(0 if report["status"] == "READY" else 2 if report["status"] == "UNSUPPORTED" else 1)


@setup_app.callback()
def setup(ctx: typer.Context,
          device: Annotated[str | None, typer.Option("--device-serial")] = None,
          skip_login: Annotated[bool, typer.Option("--skip-login-check")] = False,
          as_json: Annotated[bool, typer.Option("--json")] = False):
    if ctx.invoked_subcommand is None:
        _execute(True, device, skip_login, as_json, interactive=sys.stdin.isatty() and not as_json)


@setup_app.command("check")
def check(device: Annotated[str | None, typer.Option("--device-serial")] = None,
          skip_login: Annotated[bool, typer.Option("--skip-login-check")] = False,
          as_json: Annotated[bool, typer.Option("--json")] = False):
    """Read-only checks: official login status, ADB, Skill and Helper. No inference."""
    _execute(False, device, skip_login, as_json)


@setup_app.command("repair")
def repair(device: Annotated[str | None, typer.Option("--device-serial")] = None,
           skip_login: Annotated[bool, typer.Option("--skip-login-check")] = False,
           as_json: Annotated[bool, typer.Option("--json")] = False):
    """Repair managed settings/Skill and provision a verified Helper on the selected device."""
    _execute(True, device, skip_login, as_json, interactive=sys.stdin.isatty() and not as_json)
