"""Standard-library bootstrap shared by Windows and Linux launchers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def fingerprint():
    digest = hashlib.sha256()
    files = [ROOT / "pyproject.toml", ROOT / "skills/callisto/SKILL.md"]
    for directory in ("callisto", "artemis", "third_party", "packages/artemis-client/src"):
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in (".py", ".md", ".json", ".jsonc"))
    for path in sorted(files):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--device-serial")
    parser.add_argument("--ai-cli", choices=("codex","claude","gemini"))
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        parser.exit(1, "Python 3.12+ is required. Install it, then rerun setup.\n")
    target = ROOT / ".venv"
    python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    stamp = target / "callisto-bootstrap.json"
    expected = fingerprint()

    def run(command):
        result = subprocess.run([str(v) for v in command], cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit(result.returncode)

    if not python.is_file():
        if args.check:
            parser.exit(1, "Run setup without --check to create the local Python environment.\n")
        venv.EnvBuilder(with_pip=True).create(target)
    # Do not reuse a stale venv created with unsupported Python.
    run([python, "-c", "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)"])
    try:
        previous = json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = {}
    installed = subprocess.run([str(python), "-c", "import callisto.cli"], cwd=target,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0
    if not args.check and (not installed or previous.get("source_sha256") != expected):
        print("Installing Callisto and its Python dependencies into .venv", flush=True)
        run([python, "-m", "pip", "install", "-e", ROOT])
        run([python, "-m", "pip", "check"])
        stamp.write_text(json.dumps({"source_sha256": expected}, indent=2), encoding="utf-8")
    elif not installed:
        parser.exit(1, "Callisto is not installed; rerun setup without --check.\n")
    run([python, "-m", "pip", "check"])
    run([python, "-m", "callisto.cli", "--help"])
    command = [python, "-m", "callisto.cli", "setup"]
    if args.check:
        command.append("check")
    if args.device_serial:
        command.extend(["--device-serial", args.device_serial])
    if args.ai_cli:
        command.extend(["--ai-cli", args.ai_cli])
    if args.non_interactive:
        command.append("--json")
    run(command)


if __name__ == "__main__":
    main()
