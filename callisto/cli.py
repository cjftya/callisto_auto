"""Local-only CLI. Help and doctor never execute an AI CLI or start a server."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
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
def doctor(json_output: Annotated[bool, typer.Option("--json")] = False):
    """Check installation and configuration only; no inference or login probe."""
    provider = os.environ.get("CALLISTO_AI_CLI", "codex")
    executable = os.environ.get(f"CALLISTO_{provider.upper()}_EXECUTABLE", provider)
    from artemis.config.llm import get_default_llm_config
    config_error = None
    try:
        get_default_llm_config().validate_providers()
        if provider != "codex" and not os.environ.get("CALLISTO_MODEL"):
            config_error = "Set CALLISTO_MODEL when selecting a non-Codex CLI"
    except Exception:
        config_error = "Invalid CLI model configuration"
    implemented = provider in ("codex", "claude")
    report = {"provider": provider, "provider_implemented": implemented,
        "cli_installed": bool(shutil.which(executable)), "adb_installed": bool(shutil.which("adb")),
        "config_error": config_error, "authentication": "not_checked",
        "live_inference": "not_checked", "profile": "pro", "servers_required": False}
    typer.echo(json.dumps(report, indent=2) if json_output else
               "\n".join(f"{key}: {value}" for key, value in report.items()))
    if not implemented or config_error or not report["cli_installed"] or not report["adb_installed"]:
        raise typer.Exit(1)


@app.command()
def run(
    goal: Annotated[str, typer.Argument(help="Natural-language Android test goal")],
    device_serial: Annotated[str | None, typer.Option("--device-serial", "--device")] = None,
    traces_path: Annotated[Path, typer.Option("--traces-path")] = Path("traces"),
    output_description: Annotated[str | None, typer.Option("--expected-output")] = None,
    verification_level: Annotated[str, typer.Option("--verification-level")] = "final",
    profile: Annotated[str, typer.Option("--profile")] = "pro",
):
    """Run the original ARTEMIS Pro graph directly, with local ADB and trace output."""
    if profile != "pro":
        raise typer.BadParameter("Only the Pro execution profile is available", param_hint="--profile")
    if verification_level not in ("off", "final", "checkpoints", "strict"):
        raise typer.BadParameter("Use off, final, checkpoints or strict", param_hint="--verification-level")
    if os.environ.get("CALLISTO_FORBID_LIVE_CLI") == "1":
        raise typer.BadParameter("Live AI inference is disabled in this environment; run offline tests instead")
    from artemis.interfaces.cli.commands.run import execute_task
    session_id = str(uuid4())
    traces_path = traces_path.resolve()
    traces_path.mkdir(parents=True, exist_ok=True)
    report = {"session_id": session_id, "status": "starting", "trace_root": str(traces_path)}
    result_path = traces_path / f"{session_id}-result.json"
    previous = None
    try:
        if hasattr(signal, "SIGTERM"):
            previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
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
        content = (report.get("result") or {}).get("content")
        summary = content.get("test_summary", {}) if isinstance(content, dict) else {}
        report["test_status"] = (
            "failed" if summary.get("failed", 0) else
            "incomplete" if summary.get("inconclusive", 0) or summary.get("unchecked", 0) else
            "passed" if summary.get("passed", 0) else "not_reported"
        )
        with result_path.open("w", encoding="utf-8") as target:
            json.dump(report, target, ensure_ascii=False, indent=2, default=str)
        result_path.chmod(0o600)
    typer.echo(json.dumps({"session_id": session_id, "status": report["status"],
                           "test_status": report["test_status"],
                           "result_file": str(result_path)}, ensure_ascii=False))
    content = (report.get("result") or {}).get("content")
    summary = content.get("test_summary", {}) if isinstance(content, dict) else {}
    if report["status"] == "cancelled":
        raise typer.Exit(130)
    if report["status"] != "completed" or summary.get("failed", 0):
        raise typer.Exit(1)
    if summary.get("inconclusive", 0) or summary.get("unchecked", 0):
        raise typer.Exit(2)


# These existing commands operate on local traces and Android Helper only.
from artemis.interfaces.cli.commands.trace import trace_app
from artemis.interfaces.cli.commands.helper import helper_app
app.add_typer(trace_app, name="trace")
app.add_typer(helper_app, name="helper")


def cli():
    app()


if __name__ == "__main__":
    cli()
