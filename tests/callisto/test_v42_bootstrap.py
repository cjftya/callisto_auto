"""Bootstrap tests only launch mocked Python/pip processes."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tools import bootstrap
from tools.compare_usage import compare, load_runs


def test_bootstrap_idempotent_repair_and_read_only_check(tmp_path,monkeypatch):
    elsewhere = tmp_path / "unrelated working directory"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    tmp_path = tmp_path / "Callisto 설치 folder"
    tmp_path.mkdir()
    (tmp_path/"skills/callisto").mkdir(parents=True)
    (tmp_path/"skills/callisto/SKILL.md").write_text("skill")
    (tmp_path/"pyproject.toml").write_text("project")
    monkeypatch.setattr(bootstrap,"ROOT",tmp_path)
    def create(target):
        bindir = target/("Scripts" if bootstrap.os.name=="nt" else "bin")
        bindir.mkdir(parents=True)
        (bindir/("python.exe" if bootstrap.os.name=="nt" else "python")).touch()
    builder = Mock()
    builder.create.side_effect=create
    monkeypatch.setattr(bootstrap.venv,"EnvBuilder",lambda **kwargs:builder)
    commands=[]
    def run(command,**kwargs):
        assert kwargs["cwd"] in (tmp_path, tmp_path / ".venv")
        assert command[0] == str(tmp_path / ".venv" / (
            "Scripts/python.exe" if bootstrap.os.name == "nt" else "bin/python"))
        commands.append(command)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(bootstrap.subprocess,"run",run)
    monkeypatch.setattr(bootstrap.sys,"argv",["bootstrap.py","--check"])
    with pytest.raises(SystemExit):
        bootstrap.main()
    assert not (tmp_path/".venv").exists()
    monkeypatch.setattr(bootstrap.sys,"argv",["bootstrap.py","--non-interactive"])
    bootstrap.main()
    assert any(c[1:4]==["-m","pip","install"] for c in commands)
    assert commands[-1][-2:]==["setup","--json"]
    commands.clear()
    bootstrap.main()
    assert not any("install" in c for c in commands)
    assert builder.create.call_count==1
    assert builder.create.call_args.args == (tmp_path / ".venv",)
    assert not (elsewhere / ".venv").exists()


def test_real_usage_comparison_unknown_cache_and_unmatched(tmp_path):
    def report(tokens,passed=True):
        return {"usage":{"input_tokens":tokens,"cached_input_tokens":80,"image_attachments":3},"test_status":"passed" if passed else "failed"}
    result=compare({"a":report(100),"b":report(None),"only_before":report(5)}, {"a":report(60,False),"b":report(10)})
    assert result["median_input_reduction_percent"]==40
    assert result["unknown_token_pairs"]==1 and result["regressions"]==["a"]
    assert result["unmatched_baseline"]==["only_before"]
    assert compare({}, {})["median_input_reduction_percent"] is None
    sample=tmp_path/"sample"
    sample.mkdir()
    (sample/"one-result.json").write_text(json.dumps(report(100)))
    assert load_runs(tmp_path)["sample"]["usage"]["input_tokens"]==100
    (sample/"two-result.json").write_text("{}")
    with pytest.raises(ValueError,match="exactly one"):
        load_runs(tmp_path)
