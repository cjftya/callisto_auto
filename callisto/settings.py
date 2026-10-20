"""User-scoped non-secret settings and isolated per-run overrides."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["auto", "codex", "claude", "gemini"] = "auto"
    image_policy: Literal["off", "balanced", "quality", "economy"] = "balanced"
    device_serial: str | None = None
    codex_executable: str | None = None
    claude_executable: str | None = None
    gemini_executable: str | None = None


ENV = {"provider": "CALLISTO_AI_CLI", "image_policy": "CALLISTO_IMAGE_POLICY",
       "device_serial": "CALLISTO_DEVICE_SERIAL", "codex_executable": "CALLISTO_CODEX_EXECUTABLE",
       "claude_executable": "CALLISTO_CLAUDE_EXECUTABLE",
       "gemini_executable": "CALLISTO_GEMINI_EXECUTABLE"}
_OVERRIDES = ContextVar("callisto_settings_overrides", default={})


def settings_path():
    if os.environ.get("CALLISTO_CONFIG"):
        return Path(os.environ["CALLISTO_CONFIG"]).expanduser()
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) if os.name == "nt" else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "callisto/settings.json"


def user_settings():
    path = settings_path()
    if not path.exists():
        return {}
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(values, dict):
            # Old v4.2 config may contain hardcoded model defaults. Never apply them.
            values = {k: v for k, v in values.items() if k not in ("model", "reasoning", "provider")}
            # Before host routing, provider=codex was saved as a default on setup.
            # Never treat a stale persisted provider as the current hosting CLI.
        return Settings.model_validate(values).model_dump(exclude_unset=True)
    except (OSError, ValueError):
        raise ValueError("Invalid Callisto settings; inspect the user settings file") from None


def effective_settings(**explicit):
    values = user_settings()
    values.update({key: os.environ[var] for key, var in ENV.items() if var in os.environ})
    values.update(_OVERRIDES.get())
    values.update({key: value for key, value in explicit.items() if value is not None})
    return Settings.model_validate(values)


@contextmanager
def runtime_settings(**values):
    token = _OVERRIDES.set({**_OVERRIDES.get(), **{k: v for k, v in values.items() if v is not None}})
    try:
        yield
    finally:
        _OVERRIDES.reset(token)


def save_settings(**updates):
    validated = Settings.model_validate({**user_settings(), **updates})
    # Provider is a per-invocation host choice, never a persisted default.
    content = json.dumps(validated.model_dump(exclude={"provider"}), indent=2) + "\n"
    path = settings_path()
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8") as target:
            pending = Path(target.name)
            target.write(content)
        pending.chmod(0o600)
        pending.replace(path)
    finally:
        if pending:
            pending.unlink(missing_ok=True)
    return True
