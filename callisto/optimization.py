"""Per-invocation optimization preset; the preserved Pro sources remain unchanged.

The calling AI chooses the preset before starting an Android test. No additional
model inference is used to decide the mode. Optimizations change only the
model-bound transmission view; current observations and canonical evidence stay.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from artemis.config.paths import get_config_path
from third_party.mobile_use.utils.file import load_jsonc

MODES = ("balanced", "optimize")
_CONFIG_ENV = "ARTEMIS_ARTEMIS_JSONC"


def validate_mode(mode: str) -> str:
    if mode not in MODES:
        raise ValueError("Run mode must be balanced or optimize")
    return mode


@contextmanager
def run_mode(mode: str):
    """Override one Callisto run, restoring the user's entire configuration.

    A temporary copy of the selected ARTEMIS JSONC preserves provider/nodes/
    agent settings. Only the context *transmission* candidate becomes ready_only.
    The image historical view is separately guarded by evidence/summary checks.
    """
    mode = validate_mode(mode)
    if mode == "balanced":
        yield
        return

    source = get_config_path("artemis.jsonc")
    with source.open(encoding="utf-8") as handle:
        config = load_jsonc(handle)
    if not isinstance(config, dict):
        raise ValueError("Cannot enable optimize: invalid ARTEMIS configuration")

    # Some custom configurations store only the agent fields.
    agent = config.get("agent", config)
    if not isinstance(agent, dict):
        raise ValueError("Cannot enable optimize: invalid agent configuration")
    memory = agent.setdefault("memory", {})
    transcript = memory.setdefault("transcript", {})
    if not isinstance(transcript, dict) or transcript.get("enabled") is False:
        raise ValueError("Optimize requires an enabled transcript")
    transcript["context_policy"] = "ready_only"

    # A local, private, short-lived config copy; never rewrite the source.
    with tempfile.TemporaryDirectory(prefix="callisto-optimize-") as temp:
        path = Path(temp) / "artemis.jsonc"
        path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        path.chmod(0o600)
        overrides = {_CONFIG_ENV: str(path),
                     "CALLISTO_OPERATOR_IMAGE_POLICY": "ready_only",
                     "CALLISTO_COMPACT_TEXT": "1"}
        with patch.dict(os.environ, overrides):
            yield
