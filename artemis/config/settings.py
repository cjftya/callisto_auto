# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Application settings and environment variable configuration management."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

from artemis.config.constants import (
    DEFAULT_ADB_HOST,
    DEFAULT_ADB_PORT,
    DEFAULT_MODEL,
    DEFAULT_PROFILE,
    ENV_DATA_ENGINE_DB_PATH,
)
from artemis.config.paths import (
    GLOBAL_APP_DIR,
    get_data_engine_db_path,
    get_default_traces_path,
    get_env_file,
    get_temp_dir,
)
from third_party.mobile_use.utils.logger import get_logger

# Installed wheels load .env from the user directory, outside site-packages.
_canonical_env = get_env_file()
load_dotenv(dotenv_path=_canonical_env, verbose=True)
_global_env = GLOBAL_APP_DIR / ".env"
if _global_env.exists() and _global_env.resolve() != _canonical_env.resolve():
    load_dotenv(dotenv_path=_global_env, verbose=True)

logger = get_logger(__name__)


def is_placeholder_key(val: str | SecretStr | None) -> bool:
    """Check if an API credential is empty or an unconfigured placeholder value."""
    if val is None:
        return True
    raw_str = val.get_secret_value() if isinstance(val, SecretStr) else str(val)
    raw_str = raw_str.strip().lower()
    if not raw_str:
        return True
    if raw_str in (
        "api_key",
        "your_api_key",
        "your_api_key_here",
        "your_gemini_api_key_here",
        "your_google_cloud_vision_api_key_here",
        "your_openai_api_key_here",
        "your_anthropic_api_key_here",
        "your_openrouter_api_key_here",
        "your_xai_api_key_here",
        "none",
        "empty",
        "null",
        "undefined",
    ):
        return True
    if (
        (raw_str.startswith("your_") and raw_str.endswith("_here"))
        or (raw_str.startswith("<") and raw_str.endswith(">"))
        or (raw_str.startswith("[") and raw_str.endswith("]"))
    ):
        return True
    return False


class Settings(BaseSettings):
    """Centralized ARTEMIS runtime settings loaded from environment and .env files."""

    # Android ADB Connectivity
    ADB_HOST: str | None = Field(default=DEFAULT_ADB_HOST)
    ADB_PORT: int | None = Field(default=DEFAULT_ADB_PORT)
    ADB_DEVICE_SERIAL: str | None = None
    # UI hierarchy backend: "auto" = Accessibility Helper with UIAutomator2
    # fallback, "helper" = helper only, "uiautomator" = UIAutomator2 only.
    ARTEMIS_HIERARCHY_BACKEND: str = Field(default="auto")
    # Whether a task may install / upgrade the Accessibility Helper APK on a device
    # it holds. False = only attach to a helper installed by `artemis helper install`.
    ARTEMIS_HELPER_AUTO_INSTALL: bool = Field(default=True)

    # Execution Defaults
    PROJECT_NAME: str | None = None
    ARTEMIS_DEFAULT_PROFILE: str = Field(default=DEFAULT_PROFILE)
    ARTEMIS_DEFAULT_MODEL: str = Field(default=DEFAULT_MODEL)

    # Explorer Tool Settings (the tier itself is configured in artemis.jsonc or
    # via ARTEMIS_EXPLORER_VERSION; see artemis.config.agent.ExplorerConfig)
    EXPLORER_CACHING: bool | None = Field(
        default=None,
        description=(
            "Environment-level override for Explorer context caching; unset"
            " defers to the agent configuration and the tier default."
        ),
    )

    # LLM Reliability
    LLM_PAUSE_TIMEOUT_SECONDS: float = Field(
        default=900.0,
        description=(
            "How long a task waits in the paused state after exhausting LLM"
            " retries before failing with LLMExhaustedError. <= 0 waits"
            " forever (legacy interactive behavior)."
        ),
    )

    # Paths & Storage
    TRACES_PATH: Path = Field(default_factory=get_default_traces_path)
    DATA_ENGINE_DB_PATH: Path = Field(default_factory=get_data_engine_db_path)
    TEMP_PATH: Path = Field(default_factory=get_temp_dir)

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def GOOGLE_API_KEY(self) -> None:
        """Inert legacy attribute for callers migrating from upstream settings."""
        return None

    @GOOGLE_API_KEY.setter
    def GOOGLE_API_KEY(self, value) -> None:
        # Compatibility writes have no effect; official CLI owns authentication.
        pass

    @GOOGLE_API_KEY.deleter
    def GOOGLE_API_KEY(self) -> None:
        pass

    def get_api_key(self, provider: str) -> None:
        """Legacy accessor: Callisto neither collects nor returns API keys."""
        return None

    def set_api_key(self, provider: str, key: str, persist_to_env: bool = False) -> None:
        """Reject legacy credential writes without changing files or environment."""
        from callisto.llm_adapter.errors import UnsupportedCapability
        raise UnsupportedCapability("API key configuration is disabled; use official CLI login")


# Singleton instance
settings = Settings()

# Synchronize DATA_ENGINE_DB_PATH in environment for external sub-processes/tools
if settings.DATA_ENGINE_DB_PATH:
    os.environ[ENV_DATA_ENGINE_DB_PATH] = str(settings.DATA_ENGINE_DB_PATH)
