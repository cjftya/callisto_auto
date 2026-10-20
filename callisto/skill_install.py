"""Install the canonical Skill from source or a wheel, without running Codex."""

import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
from callisto.llm_adapter.discovery import available_providers
import tempfile
import sys

import typer

skill_app = typer.Typer(help="Install, update and inspect the Callisto Skill for supported AI CLIs.")


def canonical_skill() -> Path:
    checkout = Path(__file__).resolve().parents[1] / "skills/callisto/SKILL.md"
    if checkout.is_file():
        return checkout
    dist = distribution("callisto-auto")
    for entry in dist.files or []:
        if str(entry).replace("\\", "/").endswith("share/callisto/skills/callisto/SKILL.md"):
            path = Path(dist.locate_file(entry))
            if path.is_file():
                return path
    raise RuntimeError("Canonical Callisto Skill is missing; reinstall callisto-auto")


def skill_directory(directory: Path | None = None, *, provider="codex") -> Path:
    # Native user Skill locations; none requires an external MCP server.
    scopes = {"codex": ".agents/skills", "claude": ".claude/skills", "gemini": ".gemini/skills"}
    if provider not in scopes:
        raise ValueError("Unsupported Skill host")
    return (directory if directory is not None else Path.home() / scopes[provider]) / "callisto"


def skill_status(directory: Path | None = None, *, provider="codex") -> dict:
    dist = distribution("callisto-auto")
    target = skill_directory(directory, provider=provider)
    source_hash = hashlib.sha256(canonical_skill().read_bytes()).hexdigest()
    installed = target / "SKILL.md"
    installed_hash = hashlib.sha256(installed.read_bytes()).hexdigest() if installed.is_file() else None
    try:
        metadata = json.loads((target / "callisto-install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        metadata = {}
    managed = (isinstance(metadata, dict) and metadata.get("package") == "callisto-auto"
               and metadata.get("sha256") == installed_hash and installed_hash is not None)
    return {"path": str(target), "installed": installed_hash is not None,
            "managed": managed, "package_version": dist.version,
            "installed_version": metadata.get("version") if managed else None,
            "current": bool(managed and source_hash == installed_hash
                            and metadata.get("version") == dist.version
                            and isinstance(metadata.get("python_executable"), str)
                            and Path(metadata.get("python_executable", "")).absolute() == Path(sys.executable).absolute()),
            "discovery": "filesystem_only", "host_recognition": "not_checked"}


def install_skill(directory: Path | None = None, *, provider="codex") -> dict:
    status = skill_status(directory, provider=provider)
    target = skill_directory(directory, provider=provider)
    if target.is_symlink() or (target.exists() and not status["managed"]):
        raise ValueError("Existing unmanaged/modified Callisto Skill is preserved; choose --directory or move it first")
    content = canonical_skill().read_bytes()
    target.mkdir(parents=True, exist_ok=True)
    # Atomic per-file writes prevent truncated instructions on interruption.
    def write(name, data):
        with tempfile.NamedTemporaryFile(dir=target, delete=False) as temp:
            pending = Path(temp.name)
            temp.write(data)
        try:
            pending.replace(target / name)
        finally:
            pending.unlink(missing_ok=True)
    write("SKILL.md", content)
    write("callisto-install.json", json.dumps({"package": "callisto-auto",
        "version": status["package_version"], "python_executable": sys.executable, "sha256": hashlib.sha256(content).hexdigest()}, indent=2).encode())
    return skill_status(directory, provider=provider)


def _skill_hosts(directory: Path | None, provider: str) -> list[str]:
    """Automatically register each usable host in its own native Skill directory."""
    if provider not in ("auto", "codex", "claude", "gemini"):
        raise ValueError("Use --ai-cli auto, codex, claude or gemini")
    if provider != "auto":
        return [provider]
    hosts = available_providers()
    if not hosts:
        raise ValueError("No supported AI CLI found; install Codex, Claude Code or Gemini CLI first")
    if directory is not None and len(hosts) > 1:
        raise ValueError("With --directory and multiple AI CLIs, select one with --ai-cli")
    return hosts


@skill_app.command("install")
def install(directory: Path | None = typer.Option(None, "--directory", help="Skills parent directory"),
            provider: str = typer.Option("auto", "--ai-cli")):
    """Install Skills for all detected AI CLIs; preserve unmanaged modifications."""
    try:
        hosts = _skill_hosts(directory, provider)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    reports = {}
    for host in hosts:
        try:
            reports[host] = install_skill(directory, provider=host)
        except (OSError, ValueError, RuntimeError) as error:
            reports[host] = {"current": False, "error": str(error)}
    typer.echo(json.dumps({"hosts": reports, "current": all(v["current"] for v in reports.values())}, indent=2))
    if any(not status["current"] for status in reports.values()):
        raise typer.Exit(1)


@skill_app.command("update")
def update(directory: Path | None = typer.Option(None, "--directory"),
           provider: str = typer.Option("auto", "--ai-cli")):
    """Update all detected managed Skills, or one host with --ai-cli."""
    install(directory, provider)


@skill_app.command("status")
def status(directory: Path | None = typer.Option(None, "--directory"),
           provider: str = typer.Option("auto", "--ai-cli")):
    """Inspect Skills in detected hosts; never start an AI CLI."""
    try:
        hosts = _skill_hosts(directory, provider)
        reports = {host: skill_status(directory, provider=host) for host in hosts}
    except (OSError, ValueError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from None
    typer.echo(json.dumps({"hosts": reports, "current": all(v["current"] for v in reports.values())}, indent=2))
    if any(not report["current"] for report in reports.values()):
        raise typer.Exit(1)
