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

"""Dynamic Multi-Provider Model Router for ARTEMIS.

Provides role-based LLM/VLM dispatching, dynamic fallback chains,
and unified provider configuration across Gemini, Vertex AI, OpenAI,
Anthropic, OpenRouter, and local Ollama/vLLM endpoints.
"""

from enum import StrEnum
import hashlib
import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from artemis.config.settings import settings
from artemis.llm.google.provider import supports_thinking_level
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)


class ModelProvider(StrEnum):
    CLI = "cli"
    GOOGLE = "google"
    GEMINI = "google"
    VERTEX_AI = "vertexai"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    XAI = "xai"
    OLLAMA = "ollama"
    VLLM = "vllm"
    CUSTOM = "custom"

    @classmethod
    def from_string(cls, val: Any) -> "ModelProvider":
        """Converts a string or enum into a canonical ModelProvider.

        ``None``/empty means "use the default" (CLI); an unrecognized
        non-empty value raises instead of silently routing to Gemini with
        the wrong credentials.
        """
        if isinstance(val, cls):
            return val
        if val is None:
            return cls.CLI
        s = str(val).lower().replace("_", "").replace("-", "").strip()
        if not s:
            return cls.CLI
        mapping = {
            "cli": cls.CLI,
            "google": cls.GOOGLE,
            "gemini": cls.GOOGLE,
            "vertexai": cls.VERTEX_AI,
            "vertex": cls.VERTEX_AI,
            "openai": cls.OPENAI,
            "anthropic": cls.ANTHROPIC,
            "claude": cls.ANTHROPIC,
            "openrouter": cls.OPENROUTER,
            "xai": cls.XAI,
            "grok": cls.XAI,
            "ollama": cls.OLLAMA,
            "vllm": cls.VLLM,
            "custom": cls.CUSTOM,
        }
        provider = mapping.get(s)
        if provider is None:
            raise ValueError(
                f"Unknown LLM provider {val!r}. Valid providers: {sorted(set(mapping))}"
            )
        return provider


class ModelEndpoint(BaseModel):
    """Configuration definition for an LLM/VLM model endpoint."""

    provider: ModelProvider = Field(default=ModelProvider.CLI, description="Model provider")
    model_name: str = Field(default="gpt-6.1-sol", description="Model name identifier")
    api_key: str | None = Field(default=None, description="API Key or secret")
    api_base: str | None = Field(default=None, description="Custom API endpoint base URL")
    temperature: float = Field(default=0.0, description="Sampling temperature")
    max_tokens: int | None = Field(default=None, description="Maximum completion tokens")
    timeout_seconds: float = Field(default=60.0, description="Request timeout in seconds")
    is_multimodal: bool = Field(
        default=True, description="Whether endpoint accepts image/video inputs"
    )
    reasoning_effort: str | None = Field(
        default=None, description="Reasoning effort: 'low', 'medium', 'high'"
    )
    thinking_budget: int | None = Field(default=None, description="Thinking budget token count")
    thinking_level: str | None = Field(
        default=None, description="Thinking level: 'minimal', 'low', 'medium', 'high'"
    )
    include_thoughts: bool | None = Field(
        default=None, description="Whether to include thought traces in response"
    )
    enable_grounding: bool = Field(
        default=False,
        description="Whether to enable Google Search grounding for Gemini endpoints",
    )

    def cache_key(self) -> tuple:
        """Key the client cache by endpoint settings, hashing the API key."""
        api_key_digest = (
            hashlib.sha256(self.api_key.encode("utf-8")).hexdigest()[:16] if self.api_key else None
        )
        return (
            self.provider.value,
            self.model_name,
            self.temperature,
            self.max_tokens,
            self.timeout_seconds,
            self.thinking_budget,
            self.thinking_level,
            self.include_thoughts,
            self.reasoning_effort,
            self.enable_grounding,
            self.api_base,
            api_key_digest,
        )


class ModelFactory:
    """CLI-only model factory. Legacy API providers fail before any network call."""
    _cache: dict[tuple, BaseChatModel] = {}

    @classmethod
    def get_model(cls, endpoint: ModelEndpoint) -> BaseChatModel:
        from callisto.settings import effective_settings
        key = endpoint.cache_key() + tuple(effective_settings().model_dump().values())
        if key not in cls._cache:
            cls._cache[key] = cls.create_model(endpoint)
        return cls._cache[key]

    @classmethod
    def create_model(cls, endpoint: ModelEndpoint) -> BaseChatModel:
        if os.environ.get("ARTEMIS_FAKE_LLM") == "1":
            from artemis.llm.fake_model import FakeChatModel
            return FakeChatModel(delay_s=float(os.environ.get("ARTEMIS_FAKE_LLM_DELAY_S", "0") or 0))
        if endpoint.provider != ModelProvider.CLI:
            raise ValueError("Callisto requires provider='cli'; direct AI API providers are disabled")
        if endpoint.enable_grounding:
            from callisto.llm_adapter.errors import UnsupportedCapability
            raise UnsupportedCapability("Google Search grounding has no validated CLI equivalent")
        from callisto.llm_adapter.model import configured_model
        return configured_model(model=endpoint.model_name, timeout=endpoint.timeout_seconds,
                                reasoning_effort=endpoint.reasoning_effort)
