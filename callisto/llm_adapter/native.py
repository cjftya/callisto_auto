"""GenAI-shaped inference port. SDK types remain; direct SDK clients do not.

Text, images and function declarations map to the same CLI model contract.
Provider Files, Interactions, audio/video blobs and remote caches fail explicitly;
no synthetic cloud URI or fabricated token-count result is returned.
"""

import base64
import json
from types import SimpleNamespace

from google.genai import types
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from callisto.llm_adapter.errors import UnsupportedCapability
from callisto.llm_adapter.model import configured_model


class _Unavailable:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, operation):
        async def unavailable(*args, **kwargs):
            raise UnsupportedCapability(f"Native {self.name}.{operation} has no validated CLI equivalent")
        return unavailable


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (_text(v) for v in value)))
    return "\n".join(p.text for p in getattr(value, "parts", []) if p.text)


def convert_contents(contents, system_instruction=None):
    messages = []
    if system_instruction:
        messages.append(SystemMessage(content=_text(system_instruction)))
    if isinstance(contents, str):
        return messages + [HumanMessage(content=contents)]
    consumed = set()
    for index, content in enumerate(contents):
        if isinstance(content, str):
            messages.append(HumanMessage(content=content))
            continue
        blocks, calls, results = [], [], []
        for part in content.parts or []:
            if part.text:
                blocks.append({"type": "text", "text": part.text})
            elif part.inline_data:
                blob = part.inline_data
                if not blob.mime_type.startswith("image/"):
                    raise UnsupportedCapability("Native audio/video input has no validated CLI conversion")
                blocks.append({"type": "image_url", "image_url": {"url":
                    f"data:{blob.mime_type};base64,{base64.b64encode(blob.data).decode()}"}})
            elif part.function_call:
                call = part.function_call
                calls.append({"name": call.name, "args": call.args or {},
                              "id": call.id or f"native-{index}-{len(calls)}", "type": "tool_call"})
            elif part.function_response:
                response = part.function_response
                # Match the most recent unconsumed call by explicit ID or tool name.
                previous = [c for m in messages if isinstance(m, AIMessage) for c in m.tool_calls]
                used = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)} | consumed
                match = next((c for c in reversed(previous) if c["id"] not in used and
                              ((response.id and c["id"] == response.id) or
                               (not response.id and c["name"] == response.name))), None)
                if match is None:
                    raise UnsupportedCapability("Native function result has no matching call ID")
                consumed.add(match["id"])
                results.append(ToolMessage(content=json.dumps(response.response),
                                           tool_call_id=match["id"], name=response.name))
            else:
                raise UnsupportedCapability("Native file/media/signature part has no validated CLI conversion")
        if blocks or calls:
            messages.append(AIMessage(content=blocks, tool_calls=calls) if content.role == "model"
                            else HumanMessage(content=blocks))
        messages.extend(results)
    return messages


def _schema(value):
    """Translate GenAI's uppercase schema type enums to JSON Schema type names."""
    if isinstance(value, list):
        return [_schema(v) for v in value]
    if not isinstance(value, dict):
        return value
    result = {k: _schema(v) for k, v in value.items()}
    if isinstance(result.get("type"), str):
        result["type"] = result["type"].lower()
    return result


class Client:
    def __init__(self, *args, **kwargs):
        # Legacy api_key arguments are deliberately ignored, never read or sent.
        self.aio = SimpleNamespace(models=self, files=_Unavailable("files"), caches=_Unavailable("caches"),
                                   interactions=_Unavailable("interactions"))

    async def generate_content(self, *, model, contents, config=None):
        config = config or types.GenerateContentConfig()
        if isinstance(config, dict):
            config = types.GenerateContentConfig(**config)
        if config.cached_content:
            raise UnsupportedCapability("Native cloud context caches are not available through CLI")
        messages = convert_contents(contents, config.system_instruction)
        cli = configured_model()
        tools = []
        for tool in config.tools or []:
            if not tool.function_declarations or set(tool.model_dump(exclude_none=True)) - {"function_declarations"}:
                raise UnsupportedCapability("Native server-side tools have no CLI equivalent")
            for function in tool.function_declarations:
                parameters = function.parameters_json_schema
                if parameters is None and function.parameters is not None:
                    parameters = _schema(function.parameters.model_dump(mode="json", exclude_none=True))
                tools.append({"type": "function", "function": {"name": function.name,
                    "description": function.description or "", "parameters": parameters or {"type": "object"}}})
        choice = None
        if config.tool_config and config.tool_config.function_calling_config:
            calling = config.tool_config.function_calling_config
            mode = str(getattr(calling.mode, "value", calling.mode))
            if calling.allowed_function_names:
                allowed = set(calling.allowed_function_names)
                tools = [t for t in tools if t["function"]["name"] in allowed]
            choice = "required" if mode == "ANY" else "none" if mode == "NONE" else "auto"
        runner = cli.bind_tools(tools, tool_choice=choice) if tools else cli
        schema = config.response_json_schema
        if schema is None and config.response_schema is not None:
            if isinstance(config.response_schema, dict):
                schema = config.response_schema
            elif isinstance(config.response_schema, types.Schema):
                schema = _schema(config.response_schema.model_dump(mode="json", exclude_none=True))
            elif hasattr(config.response_schema, "model_json_schema"):
                schema = config.response_schema.model_json_schema()
            else:
                raise UnsupportedCapability("Unsupported native response schema type")
        if schema is not None:
            messages.insert(0, SystemMessage(content="Return JSON matching this schema: " + json.dumps(schema)))
        response = await runner.ainvoke(messages)
        if schema is not None:
            import jsonschema
            from callisto.llm_adapter.errors import CLIProtocolError
            try:
                jsonschema.validate(json.loads(response.content), schema)
            except (ValueError, jsonschema.ValidationError, jsonschema.SchemaError):
                raise CLIProtocolError("Native CLI response did not match the required schema") from None
        parts = [types.Part.from_text(text=response.content)] if response.content else []
        parts += [types.Part(function_call=types.FunctionCall(id=c["id"], name=c["name"], args=c["args"]))
                  for c in response.tool_calls]
        usage = None
        if response.usage_metadata:
            usage = types.GenerateContentResponseUsageMetadata(
                prompt_token_count=response.usage_metadata["input_tokens"],
                candidates_token_count=response.usage_metadata["output_tokens"],
                total_token_count=response.usage_metadata["total_tokens"])
        return types.GenerateContentResponse(candidates=[types.Candidate(
            content=types.Content(role="model", parts=parts), finish_reason="STOP")],
            usage_metadata=usage)

    async def generate_content_stream(self, **kwargs):
        # The existing native callers await this method before iterating.
        response = await self.generate_content(**kwargs)
        async def stream():
            yield response
        return stream()

    async def aclose(self):
        pass

    def close(self):
        pass
