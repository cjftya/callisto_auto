"""ZIP launchers and global registration; no pip installs, AI CLI or Android calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from callisto import skill_install


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("legacy_python", [False, True])
def test_legacy_setup_delegates_from_script_location(tmp_path, legacy_python):
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if not shell:
        pytest.skip("PowerShell is not installed on this host")
    checkout = tmp_path / "fixture install"
    (checkout / "scripts").mkdir(parents=True)
    shutil.copyfile(ROOT / "scripts/setup.ps1", checkout / "scripts/setup.ps1")
    # An inert root installer records forwarded values and a nonzero exit code.
    (checkout / "setup.ps1").write_text(
        'param([switch]$Check, [switch]$NonInteractive, [string]$DeviceSerial, [string]$AiCli)\n'
        '$PSBoundParameters | ConvertTo-Json -Compress\nexit 7\n', encoding="ascii")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    flags = (["-Python", "python"] if legacy_python else
             ["-Check", "-NonInteractive", "-DeviceSerial", "fixture serial", "-AiCli", "gemini"])
    result = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-File",
                             str(checkout / "scripts/setup.ps1"), *flags],
                            cwd=elsewhere, capture_output=True, text=True, timeout=30)
    assert "deprecated" in result.stdout
    if legacy_python:
        assert result.returncode != 0
        assert "-Python parameter is no longer supported" in result.stderr
    else:
        assert result.returncode == 7, result.stdout + result.stderr
        payload = next(line for line in result.stdout.splitlines() if line.startswith("{"))
        assert json.loads(payload) == {"Check": {"IsPresent": True}, "NonInteractive": {"IsPresent": True},
                                       "DeviceSerial": "fixture serial", "AiCli": "gemini"}
    assert not (elsewhere / ".venv").exists()


@pytest.mark.parametrize("launcher", ["setup.ps1", "setup.sh"])
def test_launcher_resolves_checkout_from_another_working_directory(tmp_path, launcher):
    if launcher.endswith(".ps1"):
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if not shell:
            pytest.skip("PowerShell is not installed on this host")
        prefix = [shell, "-NoProfile", "-NonInteractive", "-File"]
        flags = ["-Check", "-NonInteractive", "-AiCli", "gemini"]
    else:
        shell = shutil.which("sh")
        if not shell:
            pytest.skip("POSIX shell is not installed on this host")
        prefix = [shell]
        flags = ["--check", "--non-interactive", "--ai-cli", "gemini"]
    checkout = tmp_path / "Callisto 설치 folder"
    (checkout / "tools").mkdir(parents=True)
    shutil.copyfile(ROOT / launcher, checkout / launcher)
    # Exercise the real launcher with an inert bootstrap at the ZIP location.
    # Python is real; provider CLIs and dependency installation are never invoked.
    (checkout / "tools/bootstrap.py").write_text(
        "import json, sys\nfrom pathlib import Path\n"
        "print(json.dumps({'root': str(Path(__file__).resolve().parents[1]), "
        "'args': sys.argv[1:]}))\n", encoding="utf-8")
    elsewhere = tmp_path / "unrelated working directory"
    elsewhere.mkdir()
    result = subprocess.run(
        [*prefix, (checkout / launcher).as_posix(), *flags], cwd=elsewhere,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        env=dict(os.environ, CALLISTO_FORBID_LIVE_CLI="1"), check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert Path(report["root"]) == checkout
    expected = (["--check", "--ai-cli", "gemini", "--non-interactive"]
                if launcher.endswith(".ps1") else flags)
    assert report["args"] == expected
    assert not (elsewhere / ".venv").exists()


@pytest.mark.parametrize("provider,scope", [
    ("codex", ".agents"), ("claude", ".claude"), ("gemini", ".gemini")])
def test_reinstallation_updates_only_managed_skill_python(tmp_path, monkeypatch, provider, scope):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    target = tmp_path / scope / "skills/callisto"
    sentinel = tmp_path / scope / "existing-user-settings.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_bytes(b"existing settings and authentication fixture")
    source = skill_install.canonical_skill().read_bytes()
    for location in ("original install", "new 설치 location"):
        python = tmp_path / location / ".venv" / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.touch()
        monkeypatch.setattr(skill_install.sys, "executable", str(python))
        if location != "original install":
            assert not skill_install.skill_status(provider=provider)["current"]
        assert skill_install.install_skill(provider=provider)["current"]
        metadata = json.loads((target / "callisto-install.json").read_text(encoding="utf-8"))
        assert Path(metadata["python_executable"]).is_absolute()
        assert Path(metadata["python_executable"]) == python
        assert (target / "SKILL.md").read_bytes() == source
        assert {p.name for p in target.iterdir()} == {"SKILL.md", "callisto-install.json"}
        assert not target.is_symlink()
        assert sentinel.read_bytes() == b"existing settings and authentication fixture"
    (target / "SKILL.md").write_bytes(b"user modified skill")
    before = (target / "callisto-install.json").read_bytes()
    with pytest.raises(ValueError, match="preserved"):
        skill_install.install_skill(provider=provider)
    assert (target / "SKILL.md").read_bytes() == b"user modified skill"
    assert (target / "callisto-install.json").read_bytes() == before
    assert sentinel.read_bytes() == b"existing settings and authentication fixture"
