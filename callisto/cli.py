"""Local-only CLI. Help and doctor never execute an AI CLI or start a server."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
import time
from typing import Annotated
from uuid import uuid4

import typer

app = typer.Typer(name="callisto", no_args_is_help=True, invoke_without_command=True, add_completion=False,
                  pretty_exceptions_enable=False)


@app.callback()
def main(version: Annotated[bool, typer.Option("--version", "-v", is_eager=True)] = False):
    if version:
        from importlib.metadata import version as package_version
        typer.echo(f"Callisto {package_version('callisto-auto')}")
        raise typer.Exit()


@app.command()
def doctor(json_output: Annotated[bool, typer.Option("--json")] = False,
           ai_cli: Annotated[str | None, typer.Option("--ai-cli", help="Optional host filter: codex, claude or gemini")] = None):
    """Check installation and configuration only; no inference or login probe."""
    from callisto.settings import effective_settings
    from callisto.llm_adapter.discovery import available_providers, executable_command, resolve_provider
    try:
        configuration = effective_settings(provider=ai_cli)
        providers = (available_providers() if configuration.provider == "auto"
                     else [resolve_provider(configuration.provider)])
    except ValueError:
        typer.echo(json.dumps({"config_error": "Invalid AI CLI; use auto, codex, claude or gemini",
            "provider": "auto", "providers": [], "provider_implemented": False, "cli_installed": False,
            "adb_installed": bool(shutil.which("adb")), "authentication": "not_checked",
            "live_inference": "not_checked", "profile": "pro", "servers_required": False}))
        raise typer.Exit(1) from None
    provider = providers[0] if len(providers) == 1 else "auto"
    resolved = {name: bool(executable_command(name)) for name in providers}
    from artemis.config.llm import get_default_llm_config
    config_error = None
    try:
        get_default_llm_config().validate_providers()
        # Validation must not infer a different CLI from the current host.
    except Exception:
        config_error = "Invalid CLI transport configuration"
    installed = bool(providers) and all(resolved.values())
    report = {"provider": provider, "providers": providers,
        "provider_implemented": installed, "cli_installed": installed,
        "clis": resolved, "adb_installed": bool(shutil.which("adb")),
        "config_error": config_error, "authentication": "not_checked",
        "live_inference": "not_checked", "profile": "pro", "servers_required": False}
    report["launcher_supported"] = installed
    typer.echo(json.dumps(report, indent=2) if json_output else
               "\n".join(f"{key}: {value}" for key, value in report.items()))
    if config_error or not installed or not report["adb_installed"]:
        raise typer.Exit(1)


@app.command()
def run(
    goal: Annotated[str, typer.Argument(help="Natural-language Android test goal")],
    device_serial: Annotated[str | None, typer.Option("--device-serial", "--device")] = None,
    traces_path: Annotated[Path, typer.Option("--traces-path")] = Path("traces"),
    output_description: Annotated[str | None, typer.Option("--expected-output")] = None,
    verification_level: Annotated[str, typer.Option("--verification-level")] = "final",
    profile: Annotated[str, typer.Option("--profile")] = "pro",
    image_policy: Annotated[str | None, typer.Option("--image-policy", help="off, balanced, quality or economy; diagnostics compare actual CLI usage")] = None,
    ai_cli: Annotated[str | None, typer.Option("--ai-cli", help="Calling AI CLI: codex, claude or gemini")] = None,
):
    """Run an Android test with Callisto's preserved Pro engine, local ADB and traces."""
    if profile != "pro":
        raise typer.BadParameter("Only the Pro execution profile is available", param_hint="--profile")
    if verification_level not in ("off", "final", "checkpoints", "strict"):
        raise typer.BadParameter("Use off, final, checkpoints or strict", param_hint="--verification-level")
    if os.environ.get("CALLISTO_FORBID_LIVE_CLI") == "1":
        raise typer.BadParameter("Live AI inference is disabled in this environment; run offline tests instead")
    from artemis.interfaces.cli.commands.run import execute_task
    from callisto.settings import effective_settings, runtime_settings
    from callisto.usage import collect_usage, write_usage, usage_summary
    try:
        configuration = effective_settings(provider=ai_cli, image_policy=image_policy,
                                           device_serial=device_serial)
        from callisto.llm_adapter.discovery import resolve_provider
        selected_provider = resolve_provider(configuration.provider)
    except ValueError:
        raise typer.BadParameter("Invalid Callisto run settings") from None
    device_serial = configuration.device_serial
    session_id = str(uuid4())
    traces_path = traces_path.resolve()
    traces_path.mkdir(parents=True, exist_ok=True)
    report = {"session_id": session_id, "status": "starting", "trace_root": str(traces_path)}
    result_path = traces_path / f"{session_id}-result.json"
    usage_path = traces_path / f"{session_id}-usage.json"
    records = []
    previous = None
    started = time.monotonic()
    try:
        if hasattr(signal, "SIGTERM"):
            previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        with runtime_settings(provider=selected_provider, image_policy=image_policy), collect_usage() as records:
            asyncio.run(execute_task(goal=goal, device_serial=device_serial, profile="pro",
                session_id=session_id, test_name=session_id, traces_output_path_str=str(traces_path),
                output_description=output_description, verification_level=verification_level,
                result_report=report))
    except (KeyboardInterrupt, asyncio.CancelledError):
        report["status"] = "cancelled"
    except Exception as error:
        # Provider exceptions are sanitized at their boundary. Avoid raw device/log/goal data here.
        report.update(status="failed", error_type=type(error).__name__)
        from callisto.llm_adapter.errors import CLIError
        if isinstance(error, CLIError):
            report["error"] = str(error)
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)
        from callisto.verdict import settle_report
        settle_report(report)
        report["elapsed_seconds"] = round(time.monotonic() - started, 4)
        report["usage"] = usage_summary(records)
        try:
            write_usage(usage_path, records)
            report["usage_file"] = str(usage_path)
        except OSError:
            report["usage_error"] = "Could not write usage report"
            if report["status"] != "cancelled":
                report["status"] = "failed"
            settle_report(report)
        with result_path.open("w", encoding="utf-8") as target:
            json.dump(report, target, ensure_ascii=False, indent=2, default=str)
        result_path.chmod(0o600)
    typer.echo(json.dumps({"session_id": session_id, "status": report["status"],
                           "test_status": report["test_status"],
                           "exit_code": report["exit_code"],
                           "usage": report["usage"], "usage_file": report.get("usage_file"),
                           "result_file": str(result_path)}, ensure_ascii=False))
    raise typer.Exit(report["exit_code"])


# These existing commands operate on local traces and Android Helper only.
from artemis.interfaces.cli.commands.trace import trace_app
from artemis.interfaces.cli.commands.helper import helper_app
from callisto.skill_install import skill_app
from callisto.setup import setup_app
app.add_typer(trace_app, name="trace")
app.add_typer(helper_app, name="helper")
app.add_typer(skill_app, name="skill")
app.add_typer(setup_app, name="setup")


def cli():
    app()


if __name__ == "__main__":
    cli()
