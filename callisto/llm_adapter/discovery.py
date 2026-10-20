"""Find native provider binaries without executing CLIs or reading login files."""
import os
import platform
from pathlib import Path
import shutil

from callisto.settings import effective_settings


def discover_executable(provider):
    settings = effective_settings()
    explicit = getattr(settings, f"{provider}_executable", None)
    found = shutil.which(explicit or ("agy" if provider == "antigravity" else provider))
    if provider == "antigravity":
        if not found and not explicit:
            candidate = (Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "agy/bin/agy.exe"
                         if os.name == "nt" else Path.home() / ".local/bin/agy")
            try:
                if candidate.is_file():
                    found = str(candidate)
            except OSError:
                pass
        return found
    if explicit or os.name != "nt" or (found and found.lower().endswith(".exe")):
        return found
    # npm's .cmd shim is not safe for CreateProcess. Use its official vendor exe.
    roots = [Path(found).parent] if found else []
    if os.environ.get("APPDATA"):
        roots.append(Path(os.environ["APPDATA"]) / "npm")
    if provider == "codex":
        architecture = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}.get(platform.machine().lower())
        if architecture is None:
            return found
        for root in roots:
            for pattern in (f"node_modules/@openai/codex/vendor/{architecture}-pc-windows-msvc/codex/codex.exe",
                            f"node_modules/@openai/codex-*/vendor/{architecture}-pc-windows-msvc/codex/codex.exe"):
                for candidate in sorted(root.glob(pattern)):
                    if candidate.is_file():
                        return str(candidate)
    return found


def available_providers():
    """Find installed host CLIs without starting them, even if a launcher needs repair."""
    return [name for name in ("codex", "claude", "gemini", "antigravity") if discover_executable(name)]


def resolve_provider(requested=None):
    """Choose the hosting CLI, never silently fall back to Codex in multi-CLI installs."""
    choice = requested or effective_settings().provider
    if choice in ("codex", "claude", "gemini", "antigravity"):
        return choice
    if choice != "auto":
        raise ValueError("Unknown AI CLI; use --ai-cli codex, claude, gemini or antigravity")
    # A Skill must supply --ai-cli because an arbitrary child process cannot
    # read its hosting assistant's current session identity or model choice.
    installed = [name for name in ("codex", "claude", "gemini", "antigravity") if discover_executable(name)]
    if len(installed) == 1:
        return installed[0]
    raise ValueError("Cannot identify the calling AI CLI; use --ai-cli codex, claude, gemini or antigravity")


def executable_command(provider):
    """Resolve a native executable or official npm CLI entrypoint without a shell."""
    found = discover_executable(provider)
    if not found:
        return None
    if provider == "antigravity":
        # No shell/npm launcher contract has been verified for agy.
        if os.name == "nt" and not found.lower().endswith(".exe"):
            return None
        try:
            with Path(found).open("rb") as binary:
                magic = binary.read(4)
        except OSError:
            return None
        native = magic[:2] == b"MZ" if os.name == "nt" else magic == b"\x7fELF"
        return [found] if native else None
    if os.name != "nt" or found.lower().endswith(".exe"):
        return [found]
    # Windows npm .cmd launchers require cmd.exe, so execute the installed
    # JS package entrypoint with the user's own Node binary instead.
    if not found.lower().endswith((".cmd", ".bat")):
        return None
    node = shutil.which("node.exe")
    roots = [Path(found).parent]
    packages = {
        "gemini": ("@google/gemini-cli/dist/index.js",),
        "claude": ("@anthropic-ai/claude-code/cli.js",),
    }.get(provider, ())
    if not node or not packages:
        return None
    for root in roots:
        for relative in packages:
            entry = root / "node_modules" / relative
            if entry.is_file():
                return [node, str(entry)]
    return None
