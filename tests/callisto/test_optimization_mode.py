"""AI-selected, run-scoped optimization presets, without live inference."""
import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from callisto.cli import app
from callisto.optimization import run_mode, validate_mode


@pytest.fixture
def selected_config(tmp_path, monkeypatch):
    source = tmp_path / "artemis.jsonc"
    source.write_text(json.dumps({
        "default": {"provider": "cli", "fallback": {"provider": "cli"}},
        "nodes": {"operator": {"description": "unchanged"}},
        "agent": {"memory": {"transcript": {
            "enabled": True, "context_policy": "off", "start_ratio": 0.35
        }}, "pro": {"checker": {"enabled": True}}}
    }), encoding="utf-8")
    monkeypatch.setenv("ARTEMIS_ARTEMIS_JSONC", str(source))
    monkeypatch.setenv("CALLISTO_OPERATOR_IMAGE_POLICY", "shadow")
    monkeypatch.setenv("CALLISTO_COMPACT_TEXT", "0")
    return source


def test_balanced_leaves_existing_config_and_opt_in_overrides_untouched(selected_config):
    before = dict(os.environ)
    with run_mode("balanced"):
        assert dict(os.environ) == before
        from artemis.config import load_agent_config
        assert load_agent_config().memory.transcript.context_policy == "off"
    assert dict(os.environ) == before


def test_optimize_uses_transient_full_config_and_restores_environment(selected_config):
    original = selected_config.read_bytes()
    before = {key: os.environ.get(key) for key in (
        "ARTEMIS_ARTEMIS_JSONC", "CALLISTO_OPERATOR_IMAGE_POLICY", "CALLISTO_COMPACT_TEXT")}
    with run_mode("optimize"):
        path = Path(os.environ["ARTEMIS_ARTEMIS_JSONC"])
        assert path != selected_config
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["default"]["provider"] == "cli"
        assert data["nodes"]["operator"]["description"] == "unchanged"
        assert data["agent"]["pro"]["checker"]["enabled"] is True
        assert data["agent"]["memory"]["transcript"]["start_ratio"] == 0.35
        assert data["agent"]["memory"]["transcript"]["context_policy"] == "ready_only"
        from artemis.config import load_agent_config
        assert load_agent_config().memory.transcript.context_policy == "ready_only"
        assert os.environ["CALLISTO_OPERATOR_IMAGE_POLICY"] == "ready_only"
        assert os.environ["CALLISTO_COMPACT_TEXT"] == "1"
    assert not path.exists()
    assert selected_config.read_bytes() == original
    assert {key: os.environ.get(key) for key in before} == before


def test_optimize_rejects_disabled_transcript_without_changing_source(tmp_path, monkeypatch):
    source = tmp_path / "disabled.jsonc"
    source.write_text('{"agent":{"memory":{"transcript":{"enabled":false}}}}', encoding="utf-8")
    monkeypatch.setenv("ARTEMIS_ARTEMIS_JSONC", str(source))
    original = source.read_bytes()
    with pytest.raises(ValueError, match="requires an enabled transcript"):
        with run_mode("optimize"):
            pytest.fail("Unexpected entry")
    assert source.read_bytes() == original


@pytest.mark.parametrize("mode", ["auto", "economy", "unsafe", ""])
def test_invalid_mode_fails_closed_without_running_pro(mode):
    with pytest.raises(ValueError, match="balanced or optimize"):
        validate_mode(mode)
    result = CliRunner().invoke(app, ["run", "battery test", "--mode", mode])
    assert result.exit_code != 0
    assert "balanced or optimize" in result.output


def test_balanced_is_cli_default_even_when_live_execution_is_blocked(monkeypatch):
    monkeypatch.setenv("CALLISTO_FORBID_LIVE_CLI", "1")
    result = CliRunner().invoke(app, ["run", "battery test"])
    assert result.exit_code != 0
    assert "Live AI inference is disabled" in result.output
