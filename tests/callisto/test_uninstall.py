"""Destructive lifecycle checks operate exclusively on temporary source installs."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import venv

import pytest


SOURCE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("uninstall", SOURCE / "tools/uninstall.py")
uninstall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uninstall)


@pytest.fixture
def install(tmp_path, monkeypatch):
    home = tmp_path / "user"
    home.mkdir()
    root = home / "tools" / "Callisto 공백"
    root.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("CALLISTO_CONFIG", raising=False)
    for name in ("setup.ps1", "setup.sh", "uninstall.ps1", "uninstall.sh", "tools/bootstrap.py", "tools/uninstall.py", "callisto/cli.py", "skills/callisto/SKILL.md", "pyproject.toml"):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, target)
    (root / "artemis/graph").mkdir(parents=True)
    (root / ".venv").mkdir()
    (root / "personal-trace.txt").write_text("backup required")
    return root, home


def register(home, root, scope=uninstall.SCOPES[0]):
    target = home / scope
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("managed instructions", encoding="utf-8")
    metadata = {"package": "callisto-auto", "sha256": uninstall.digest(target / "SKILL.md"),
                "python_executable": str(root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))}
    (target / "callisto-install.json").write_text(json.dumps(metadata), encoding="utf-8")
    return target


def config_path(home):
    return home / ("AppData" if os.name == "nt" else ".config") / "callisto/settings.json"


def settings(home):
    path = config_path(home)
    path.parent.mkdir(parents=True)
    path.write_text('{"image_policy":"balanced"}', encoding="utf-8")
    return path


def test_full_removal_and_preserved_external_data(install):
    root, home = install
    target = register(home, root)
    config = settings(home)
    external = home / "external-trace.txt"
    external.write_text("keep")
    auth = home / ".agents/auth.json"
    auth.write_text("do not inspect or remove")
    plan = uninstall.make_plan(root, True)
    report = uninstall.execute(plan)
    assert report["status"] == "complete"
    assert not root.exists() and not target.exists() and not config.parent.exists()
    assert external.read_text() == "keep" and auth.exists()


@pytest.mark.parametrize("variation", ["other", "modified", "extra", "corrupt", "list", "relative"])
def test_unmanaged_or_other_install_is_preserved(install, variation):
    root, home = install
    target = register(home, root if variation != "other" else home / "other")
    metadata = target / "callisto-install.json"
    if variation == "modified":
        (target / "SKILL.md").write_text("custom")
    elif variation == "extra":
        (target / "notes.txt").write_text("personal")
    elif variation == "corrupt":
        metadata.write_text("{")
    elif variation == "list":
        metadata.write_text("[]")
    elif variation == "relative":
        data = json.loads(metadata.read_text())
        data["python_executable"] = ".venv/bin/python"
        metadata.write_text(json.dumps(data))
    config = settings(home)
    plan = uninstall.make_plan(root, True)
    assert not plan["targets"]
    report = uninstall.execute(plan)
    assert report["status"] == "complete" and target.exists() and config.exists()


def test_default_custom_and_unknown_config_preserved(install, monkeypatch):
    root, home = install
    config = settings(home)
    assert uninstall.make_plan(root)["targets"] == []
    monkeypatch.setenv("CALLISTO_CONFIG", str(home / "shared.json"))
    assert uninstall.make_plan(root, True)["targets"] == []
    monkeypatch.delenv("CALLISTO_CONFIG")
    (config.parent / "user.txt").write_text("keep")
    assert uninstall.make_plan(root, True)["targets"] == []


def test_changed_approval_rejected_without_deletion(install):
    root, home = install
    target = register(home, root)
    plan = uninstall.make_plan(root)
    (target / "SKILL.md").write_text("edited after approval")
    with pytest.raises(ValueError, match="scope changed"):
        uninstall.execute(plan)
    assert root.exists() and target.exists()


def test_invalid_roots(install):
    root, home = install
    for invalid in (home, Path(home.anchor), home.parent, home / "other"):
        with pytest.raises((ValueError, OSError)):
            uninstall.validate_root(invalid)
    (root / "setup.sh").unlink()
    with pytest.raises(ValueError, match="Incomplete"):
        uninstall.validate_root(root)


def test_junction_rejected_and_interior_link_not_followed(install):
    root, home = install
    outside = home / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    link = root / "linked-data"
    if os.name == "nt":
        # Windows junction creation requires no symlink privilege; no deletion via cmd.
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="Linked"):
        uninstall.no_links(link / "keep.txt")
    uninstall.execute(uninstall.make_plan(root))
    assert (outside / "keep.txt").read_text() == "keep"


def test_partial_failure_report(install, monkeypatch):
    root, home = install
    target = register(home, root)
    plan = uninstall.make_plan(root)
    def denied(path):
        raise PermissionError("locked test path")
    monkeypatch.setattr(uninstall, "remove_tree", denied)
    report = uninstall.execute(plan)
    assert report["status"] == "failed" and len(report["failed"]) == 2
    assert root.exists() and target.exists()


def test_busy_process_refuses(install, monkeypatch):
    root, _ = install
    monkeypatch.setattr(uninstall, "processes", lambda: [(987654, 1, str(root / ".venv/bin/python") + " -m callisto.cli run")])
    with pytest.raises(ValueError, match="987654"):
        uninstall.check_busy(root)


def test_noninteractive_and_wrong_confirmation_preserve(install):
    root, home = install
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    for extra in ([], ["--confirm-root", "wrong"]):
        result = subprocess.run([sys.executable, str(root / "tools/uninstall.py"), *extra], env=env, input="", capture_output=True, text=True)
        assert result.returncode == 1
        assert root.exists()


@pytest.mark.parametrize("launcher", ["system", "venv", "native"])
def test_external_worker_deletes_only_temporary_install(install, tmp_path, launcher):
    root, home = install
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), TEMP=str(tmp_path), TMP=str(tmp_path), TMPDIR=str(tmp_path))
    command = [sys.executable, str(root / "tools/uninstall.py"), "--confirm-root", str(root)]
    if launcher == "venv":
        venv.EnvBuilder(with_pip=False).create(root / ".venv")
        command[0] = str(root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
    elif launcher == "native":
        command = (["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(root / "uninstall.ps1"), "-ConfirmRoot", str(root)]
                   if os.name == "nt" else ["sh", str(root / "uninstall.sh"), "--confirm-root", str(root)])
    result = subprocess.run(command,
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SCHEDULED" in result.stdout
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        reports = list(tmp_path.glob("callisto-uninstall-*/result.json"))
        if reports:
            report = json.loads(reports[0].read_text(encoding="utf-8"))
            assert report["status"] == "complete", report
            assert not root.exists()
            assert not (reports[0].parent / "worker.py").exists()
            return
        time.sleep(0.2)
    pytest.fail("External worker did not produce a final result")


def test_decline_is_noop(install, monkeypatch):
    root, _ = install
    monkeypatch.setattr(uninstall, "__file__", str(root / "tools/uninstall.py"))
    monkeypatch.setattr(sys, "argv", ["uninstall.py"])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    monkeypatch.setattr(uninstall, "check_busy", lambda *args: None)
    assert uninstall.main() == 1
    assert root.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell launcher")
@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh"])
def test_powershell_launcher_dry_run(install, tmp_path, shell):
    root, home = install
    if not shutil.which(shell):
        pytest.skip(f"{shell} is not installed")
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-File", str(root / "uninstall.ps1"), "-DryRun"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ENTIRE installation" in result.stdout and root.exists()


@pytest.mark.skipif(os.name == "nt", reason="Linux shell launcher")
def test_shell_launcher_dry_run(install, tmp_path):
    root, home = install
    env = dict(os.environ, HOME=str(home))
    result = subprocess.run(["sh", str(root / "uninstall.sh"), "--dry-run"], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ENTIRE installation" in result.stdout and root.exists()
