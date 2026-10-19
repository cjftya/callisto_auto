"""Find native provider binaries without executing CLIs or reading login files."""
import os
import platform
from pathlib import Path
import shutil

from callisto.settings import effective_settings


def discover_executable(provider):
    settings = effective_settings()
    explicit = getattr(settings, f"{provider}_executable", None)
    found = shutil.which(explicit or provider)
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
