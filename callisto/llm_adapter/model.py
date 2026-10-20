"""LangChain model boundary; ARTEMIS retains all planning and tool execution."""

import asyncio
import json
from pathlib import Path
import tempfile
import weakref
import time

import jsonschema
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from callisto.llm_adapter.codec import encode_messages, encode_prompt
from callisto.llm_adapter.errors import CLIProtocolError, UnsupportedCapability
from callisto.llm_adapter.process import run_process
from callisto.llm_adapter.providers import build_stdin, command_for, decode_result
from callisto.settings import effective_settings
from callisto.llm_adapter.discovery import resolve_provider
from callisto.usage import agent_label, stage_label, record_call

_LOOP_LOCKS = weakref.WeakKeyDictionary()


def _lock(provider):
    locks = _LOOP_LOCKS.setdefault(asyncio.get_running_loop(), {})
    return locks.setdefault(provider, asyncio.Lock())


def response_schema(tools):
    names = [tool["function"]["name"] for tool in tools]
    return {
        "type": "object", "additionalProperties": False,
        "properties": {
            "content": {"type": "string"},
            "tool_calls": {"type": "array", "maxItems": 64,
                "items": {"type": "object", "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "name": {"type": "string", **({"enum": names} if names else {})},
                        "args_json": {"type": "string"},
                    }, "required": ["id", "name", "args_json"]}},
        }, "required": ["content", "tool_calls"],
    }


class CLIChatModel(BaseChatModel):
    provider: str = "codex"
    model_name: str | None = None
    timeout_seconds: float = Field(default=180, gt=0)
    reasoning_effort: str | None = None
    image_policy: str = "balanced"

    @property
    def _llm_type(self):
        return "callisto-cli"

    @property
    def _identifying_params(self):
        return {"provider": self.provider, "model": self.model_name,
                "reasoning": self.reasoning_effort, "image_policy": self.image_policy}

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        converted = [convert_to_openai_tool(tool) for tool in tools]
        names = [t["function"]["name"] for t in converted]
        if len(names) != len(set(names)):
            raise ValueError("Tool names must be unique")
        return self.bind(tools=converted, tool_choice=tool_choice, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return asyncio.run(self._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs))

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        started = time.monotonic()
        metrics = {"agent": agent_label(run_manager), "stage": stage_label(run_manager), "provider": self.provider,
                   "model": self.model_name, "status": "failed", "cli_usage": {}}
        try:
            result = await self._infer(messages, stop=stop, metrics=metrics, **kwargs)
            metrics["status"] = "completed"
            result.generations[0].message.response_metadata["image_metrics"] = {
                k: v for k, v in metrics.items() if k.startswith("image")}
            return result
        finally:
            metrics["elapsed_seconds"] = round(time.monotonic() - started, 4)
            record_call(metrics)

    async def _infer(self, messages, stop=None, metrics=None, **kwargs):
        if stop:
            raise UnsupportedCapability("CLI stop sequences are not supported; response truncation is forbidden")
        provider = resolve_provider(self.provider)
        from callisto.llm_adapter.providers import require_inference_support
        require_inference_support(provider)
        if metrics is not None:
            metrics["provider"] = provider
        tools = kwargs.get("tools", [])
        tool_choice = kwargs.get("tool_choice")
        if kwargs.get("google_search") or kwargs.get("tool_config"):
            raise UnsupportedCapability("Native server-side tools require a validated CLI equivalent")
        if self.reasoning_effort not in (None, "none", "minimal", "low", "medium", "high", "xhigh", "ultra"):
            raise ValueError("Invalid CLI reasoning effort")
        schema = response_schema(tools)
        async with asyncio.timeout(self.timeout_seconds):
            async with _lock(provider):
                with tempfile.TemporaryDirectory(prefix="callisto-inference-") as temp:
                    directory = Path(temp)
                    schema_path = directory / "response-schema.json"
                    schema_path.write_text(json.dumps(schema), encoding="utf-8")
                    history, images = encode_messages(messages, directory, policy=self.image_policy, metrics=metrics)
                    prompt = encode_prompt(history, tools, tool_choice, schema)
                    command = command_for(provider, self.model_name, directory, images,
                                          schema_path, self.reasoning_effort)
                    result = await run_process(command, stdin=build_stdin(provider, prompt, images), cwd=str(directory),
                                               timeout=self.timeout_seconds, provider=provider)
                    text, usage = decode_result(provider, result)
                    usage = {key: value for key, value in usage.items()
                             if key in ("input_tokens", "output_tokens", "cached_input_tokens",
                                        "cache_read_input_tokens", "cache_creation_input_tokens")
                             and isinstance(value, int) and not isinstance(value, bool) and value >= 0} if isinstance(usage, dict) else {}
                    metrics["cli_usage"] = usage
                    message = self._message(text, tools, tool_choice, kwargs.get("parallel_tool_calls", True))
                    message.response_metadata = {"provider": provider, "model_name": self.model_name,
                        "transport": "authenticated-cli", "cli_usage": usage}
                    # Never invent usage. Cache reads in Codex are a subset of input tokens.
                    if isinstance(usage, dict):
                        input_tokens = usage.get("input_tokens")
                        output_tokens = usage.get("output_tokens")
                        if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                            message.usage_metadata = {"input_tokens": input_tokens,
                                "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens}
                    return ChatResult(generations=[ChatGeneration(message=message)])

    @staticmethod
    def _message(text, tools, tool_choice, parallel=True):
        try:
            payload = json.loads(text)
            jsonschema.validate(payload, response_schema(tools))
            declarations = {t["function"]["name"]: t["function"] for t in tools}
            calls = []
            seen = set()
            for item in payload["tool_calls"]:
                if item["id"] in seen or item["name"] not in declarations:
                    raise ValueError
                seen.add(item["id"])
                args = json.loads(item["args_json"])
                if not isinstance(args, dict):
                    raise ValueError
                jsonschema.validate(args, declarations[item["name"]].get("parameters", {"type": "object"}))
                calls.append({"id": item["id"], "name": item["name"], "args": args, "type": "tool_call"})
            required = tool_choice in ("any", "required") if isinstance(tool_choice, str) else False
            named = None
            if isinstance(tool_choice, str) and tool_choice not in ("auto", "any", "required", "none"):
                named = tool_choice
            elif isinstance(tool_choice, dict):
                named = tool_choice.get("function", {}).get("name")
            if (required and not calls) or (tool_choice == "none" and calls):
                raise ValueError
            if named and (not calls or any(c["name"] != named for c in calls)):
                raise ValueError
            if not parallel and len(calls) > 1:
                raise ValueError
            if not calls and not payload["content"].strip():
                raise ValueError
            return AIMessage(content=payload["content"], tool_calls=calls)
        except (ValueError, TypeError, KeyError, jsonschema.ValidationError, jsonschema.SchemaError):
            raise CLIProtocolError("CLI response violated the agent JSON/tool-call contract") from None


def configured_model(*, model=None, timeout=180, reasoning_effort=None):
    """Ignore legacy routing hints; inference uses the provider CLI defaults."""
    settings = effective_settings()
    return CLIChatModel(provider=settings.provider, model_name=None,
                        timeout_seconds=timeout, reasoning_effort=None,
                        image_policy=settings.image_policy)
