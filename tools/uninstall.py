"""Conservative source-install uninstaller. No imports from the installed engine."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


SCOPES = (".agents/skills/callisto", ".claude/skills/callisto", ".gemini/skills/callisto", ".gemini/antigravity-cli/skills/callisto")


def absolute(path):
    return Path(os.path.abspath(path))


def no_links(path):
    """Check lexical ancestors too; resolve() alone would hide a junction."""
    path = absolute(path)
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError(f"Linked path is preserved: {part}")
    return path


def validate_root(root):
    root = no_links(root)
    home = Path.home().resolve()
    containers = [home / name for name in ("Documents", "Desktop", "Downloads", "Pictures", "Videos", "Music", "AppData", ".config", ".agents", ".claude", ".gemini")]
    if any(root == path or root in path.parents for path in containers):
        raise ValueError(f"Protected user directory: {root}")
    protected = [home, Path(root.anchor)]
    if os.name == "nt":
        protected += [Path(os.environ.get(key, fallback)) for key, fallback in (
            ("SystemRoot", "C:/Windows"), ("ProgramFiles", "C:/Program Files"),
            ("ProgramFiles(x86)", "C:/Program Files (x86)"), ("ProgramData", "C:/ProgramData"))]
    else:
        protected += [Path(p) for p in ("/usr", "/bin", "/sbin", "/etc", "/var", "/lib", "/boot", "/dev", "/proc", "/sys")]
    for item in protected:
        if root == item or root in item.parents or (item != home and item != Path(root.anchor) and item in root.parents):
            raise ValueError(f"Protected installation path: {root}")
    for marker in ("setup.ps1", "setup.sh", "uninstall.ps1", "uninstall.sh", "tools/bootstrap.py",
                   "tools/uninstall.py", "callisto/cli.py", "artemis/graph", "skills/callisto/SKILL.md"):
        target = no_links(root / marker)
        if not target.exists():
            raise ValueError(f"Incomplete source installation; use manual removal: {target}")
    if 'name = "callisto-auto"' not in no_links(root / "pyproject.toml").read_text(encoding="utf-8"):
        raise ValueError("Callisto package metadata did not match")
    return root


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_target(path, root):
    no_links(path)
    if set(p.name for p in path.iterdir()) != {"SKILL.md", "callisto-install.json"}:
        raise ValueError("extra or missing files; user-managed Skill")
    metadata = json.loads((path / "callisto-install.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("package") != "callisto-auto":
        raise ValueError("unmanaged metadata")
    for child in path.iterdir():
        no_links(child)
        if not child.is_file():
            raise ValueError("non-file Skill content")
    expected = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    # Lexical comparison is intentional: Linux venv Python normally symlinks to system Python.
    registered = metadata.get("python_executable")
    if not isinstance(registered, str) or not Path(registered).is_absolute() or absolute(registered) != expected:
        raise ValueError("points to another installation or invalid Python")
    if metadata.get("sha256") != digest(path / "SKILL.md"):
        raise ValueError("modified Skill")
    return {"path": str(path), "kind": "skill", "hashes": {p.name: digest(p) for p in path.iterdir()}}


def make_plan(root, remove_settings=False):
    root = validate_root(root)
    targets, preserved = [], []
    other = False
    for scope in SCOPES:
        path = Path.home() / scope
        if not os.path.lexists(path):
            continue
        try:
            targets.append(skill_target(path, root))
        except (OSError, ValueError) as error:
            other = True
            preserved.append({"path": str(path), "reason": str(error)})
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) if os.name == "nt" else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    config = absolute(base / "callisto/settings.json")
    if os.environ.get("CALLISTO_CONFIG"):
        preserved.append({"path": str(absolute(Path(os.environ["CALLISTO_CONFIG"]).expanduser())), "reason": "custom/shared CALLISTO_CONFIG; inspect manually"})
    if os.path.lexists(config.parent):
        try:
            no_links(config)
            if not remove_settings or other or os.environ.get("CALLISTO_CONFIG"):
                raise ValueError("shared settings; opt in with --remove-settings only after checking other installs")
            if set(p.name for p in config.parent.iterdir()) != {"settings.json"}:
                raise ValueError("unknown files in config directory; inspect manually")
            content = json.loads(config.read_text(encoding="utf-8"))
            keys = {"provider", "model", "reasoning", "image_policy", "device_serial", "codex_executable", "claude_executable", "gemini_executable", "antigravity_executable"}
            if not isinstance(content, dict) or not set(content) <= keys:
                raise ValueError("unrecognized settings; inspect manually")
            targets.append({"path": str(config), "kind": "settings", "sha256": digest(config)})
        except (OSError, ValueError) as error:
            preserved.append({"path": str(config.parent), "reason": str(error)})
    for item in targets + preserved:
        path = absolute(item["path"])
        if path == root or root in path.parents or path in root.parents:
            raise ValueError(f"Install overlaps user Skill/config storage: {path}")
    identity = root.stat()
    return {"root": str(root), "root_identity": [identity.st_dev, identity.st_ino],
            "targets": targets, "preserved": preserved, "remove_settings": remove_settings}


def processes():
    """Inventory without provider execution, credentials, or engine imports."""
    if os.name == "nt":
        script = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-CimInstance Win32_Process -ErrorAction Stop | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                capture_output=True, encoding="utf-8", errors="replace", check=True, timeout=30)
        data = json.loads(result.stdout)
        return [(int(p["ProcessId"]), int(p["ParentProcessId"]), (p.get("ExecutablePath") or "") + " " + (p.get("CommandLine") or "")) for p in (data if isinstance(data, list) else [data])]
    return posix_processes()


def posix_processes(proc=Path("/proc")):
    if not (proc / "self/cmdline").exists():
        raise ValueError("Process inventory unavailable; stop Callisto and use manual removal")
    result = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            parent = int((entry / "stat").read_text().rsplit(")", 1)[1].split()[1])
            try:
                executable = os.readlink(entry / "exe")
            except PermissionError:
                # Non-dumpable same-user services can expose cmdline/stat but
                # restrict exe via ptrace policy. Readable command lines still
                # identify source/venv launches and `-m callisto` invocations.
                executable = ""
            result.append((int(entry.name), parent, executable + " " + command))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            # Other users' processes cannot own this per-user installation.
            if entry.stat().st_uid == os.getuid():
                raise ValueError(f"Cannot inspect same-user process {entry.name}") from None
    return result


def check_busy(root, ignored=()):
    inventory = processes()
    parents = {pid: (parent, command) for pid, parent, command in inventory}
    ancestors = []
    cursor = os.getpid()
    while cursor in parents and cursor not in ancestors:
        ancestors.append(cursor)
        cursor = parents[cursor][0]
    # Windows venv Python may be a forwarding executable waiting for the real
    # interpreter. It is part of this invocation, not a competing Callisto run.
    ignore = {os.getpid()}
    for pid in ancestors[1:]:
        command = parents[pid][1].casefold()
        if command.startswith(str(Path(sys.executable)).casefold() + " ") and str(absolute(__file__)).casefold() in command:
            ignore.add(pid)
        else:
            break
    for pid in ignored:
        if pid not in ancestors:
            raise ValueError("Launcher PID is not an ancestor of this uninstaller")
        ignore.update(ancestors[:ancestors.index(pid) + 1])
    wait_pids = sorted(ignore)
    # Inventory helpers (CIM) are descendants of this uninstaller.
    for _ in range(len(inventory)):
        ignore.update(pid for pid, parent, _ in inventory if parent in ignore)
    needle = str(root).replace("\\", "/").casefold()
    busy = []
    for pid, _, command in inventory:
        text = command.replace("\\", "/").casefold()
        if pid not in ignore and (needle in text or "-m callisto" in text or "-m artemis" in text):
            busy.append(pid)
    if busy:
        raise ValueError(f"Stop Callisto/setup processes and retry. PIDs: {busy}")
    return wait_pids


def remove_tree(path):
    # Python 3.12+ rmtree unlinks interior symlinks/junctions without traversing them.
    no_links(path)
    shutil.rmtree(path)


def execute(plan):
    current = make_plan(Path(plan["root"]), plan["remove_settings"])
    if current != plan:
        raise ValueError("Removal scope changed after approval; run a new preview")
    removed, failed = [], []
    for target in plan["targets"]:
        path = Path(target["path"])
        try:
            if target["kind"] == "skill":
                if skill_target(path, Path(plan["root"])) != target:
                    raise ValueError("Skill changed after approval")
                remove_tree(path)
            else:
                no_links(path)
                if digest(path) != target["sha256"]:
                    raise ValueError("Settings changed after approval")
                path.unlink()
                try:
                    path.parent.rmdir()  # only empty dedicated directory
                except OSError:
                    pass
            removed.append(str(path))
        except (OSError, ValueError) as error:
            failed.append({"path": str(path), "reason": str(error)})
    root = validate_root(Path(plan["root"]))
    try:
        remove_tree(root)
        removed.append(str(root))
    except OSError as error:
        failed.append({"path": str(root), "reason": str(error)})
    return {"status": "failed" if failed else "complete", "removed": removed, "failed": failed, "preserved": plan["preserved"]}


def worker(job_path):
    job_path = Path(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    result_path = job_path.parent / "result.json"
    try:
        deadline = time.monotonic() + 60
        while set(job["wait_pids"]) & {p[0] for p in processes()}:
            if time.monotonic() > deadline:
                raise ValueError("Launcher still running; installation preserved. Close launcher and retry.")
            time.sleep(0.5)
        check_busy(Path(job["plan"]["root"]))
        result = execute(job["plan"])
    except Exception as error:
        result = {"status": "failed", "failed": [{"path": job["plan"]["root"], "reason": str(error)}]}
    result["next_action"] = "Inspect failed/preserved paths; use README manual removal for partial installs. Never retry broad deletion blindly."
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    job_path.unlink(missing_ok=True)
    Path(__file__).unlink(missing_ok=True)
    return 0 if result["status"] == "complete" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove-settings", action="store_true", help="Remove default settings only after checking shared installs")
    parser.add_argument("--confirm-root", help="Exact absolute root, only after explicit final user approval")
    parser.add_argument("--launcher-pid", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        return worker(args.worker)
    try:
        root = absolute(Path(__file__).parent.parent)
        plan = make_plan(root, args.remove_settings)
        ignored = [args.launcher_pid] if args.launcher_pid else []
        wait_pids = check_busy(root, ignored)
        print(json.dumps(plan, ensure_ascii=True, indent=2), flush=True)
        print("WARNING: The ENTIRE installation, .venv, extra personal files and internal Traces will be deleted. Back up first.", flush=True)
        print("Preserved: system Python, Android SDK/ADB/device/Helper app, AI CLIs/login, external files/Traces and other installs.", flush=True)
        if args.dry_run:
            return 0
        if args.confirm_root is not None:
            if args.confirm_root != str(root):
                raise ValueError("--confirm-root must exactly match the preview root")
        elif not sys.stdin.isatty() or input(f"Type the full installation path to approve permanent removal: {root}\n> ") != str(root):
            raise ValueError("No explicit approval; nothing deleted")
        if make_plan(root, args.remove_settings) != plan:
            raise ValueError("Scope changed; preview again")
        # Use base Python, not a venv interpreter whose DLLs may lock the installation.
        python = no_links(Path(getattr(sys, "_base_executable", sys.executable)).resolve())
        if python == root or root in python.parents:
            raise ValueError("External system Python required; use README manual removal")
        directory = Path(tempfile.mkdtemp(prefix="callisto-uninstall-"))
        if root in directory.resolve().parents:
            directory.rmdir()
            raise ValueError("Temporary worker must be outside the installation; change TEMP/TMPDIR")
        script = directory / "worker.py"
        shutil.copyfile(__file__, script)
        job_path = directory / "job.json"
        job_path.write_text(json.dumps({"plan": plan, "wait_pids": wait_pids}), encoding="utf-8")
        options = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        with (directory / "output.log").open("wb") as log:
            subprocess.Popen([str(python), "-I", str(script), "--worker", str(job_path)], cwd=directory,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True, **options)
        print(f"Removal SCHEDULED (not yet complete). Exit this launcher; check: {directory / 'result.json'}", flush=True)
        print(f"Worker output: {directory / 'output.log'}. Temporary scripts self-delete; keep result until reviewed.", flush=True)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"ACTION_REQUIRED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
