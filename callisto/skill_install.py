"""Install the canonical Skill from source or a wheel, without running Codex."""

import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path
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


@skill_app.command("install")
def install(directory: Path | None = typer.Option(None, "--directory", help="Skills parent directory"),
            provider: str = typer.Option("codex", "--ai-cli")):
    """Install or update a previously managed Skill; preserve user modifications."""
    try:
        typer.echo(json.dumps(install_skill(directory, provider=provider), indent=2))
    except (OSError, ValueError, RuntimeError) as error:
        raise typer.BadParameter(str(error)) from None


@skill_app.command("update")
def update(directory: Path | None = typer.Option(None, "--directory"),
           provider: str = typer.Option("codex", "--ai-cli")):
    """Update the managed Skill to this installed package version."""
    install(directory, provider)


@skill_app.command("status")
def status(directory: Path | None = typer.Option(None, "--directory"),
           provider: str = typer.Option("codex", "--ai-cli")):
    """Inspect version/hash and discovery path; never start the host AI CLI."""
    report = skill_status(directory, provider=provider)
    typer.echo(json.dumps(report, indent=2))
    raise typer.Exit(0 if report["current"] else 1)
