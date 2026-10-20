"""Explicit opt-in acceptance test on the selected CLI execution machine.

This script invokes a real, authenticated AI CLI only with --allow-live-cli.
Offline CI uses tests/callisto instead.
"""

import argparse
import asyncio
import base64
from io import BytesIO
import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from PIL import Image
from pydantic import BaseModel

from callisto.llm_adapter.model import configured_model
from callisto.settings import runtime_settings


class Sentinel(BaseModel):
    value: int


class Colors(BaseModel):
    left: str
    right: str


async def verify():
    model = configured_model(timeout=180)
    results = {"text": False, "json_schema": False, "tool_calls": False,
               "tool_result_roundtrip": False, "multi_turn": False, "image": False}
    try:
        response = await model.ainvoke("Reply exactly CALLISTO_OK in content. Make no tool calls.")
        results["text"] = response.content.strip() == "CALLISTO_OK"
        response = await model.with_structured_output(Sentinel).ainvoke("Return value 731.")
        results["json_schema"] = response.value == 731
        tool = {"type": "function", "function": {"name": "echo_value",
            "description": "Echo a number through the external ARTEMIS runtime",
            "parameters": {"type": "object", "properties": {"value": {"type": "integer"}},
                           "required": ["value"], "additionalProperties": False}}}
        request = HumanMessage(content="Call echo_value with value 731. Do not execute it yourself.")
        response = await model.bind_tools([tool], tool_choice="echo_value").ainvoke([request])
        results["tool_calls"] = len(response.tool_calls) == 1 and response.tool_calls[0]["args"] == {"value": 731}
        if results["tool_calls"]:
            followup = await model.ainvoke([request, response,
                ToolMessage(content="LOCAL_RESULT_731", tool_call_id=response.tool_calls[0]["id"]),
                HumanMessage(content="Reply with exactly the tool result text, without any tool calls.")])
            results["tool_result_roundtrip"] = followup.content.strip() == "LOCAL_RESULT_731"
        response = await model.ainvoke([SystemMessage(content="Remember the user's reference number."),
            HumanMessage(content="The reference number is 49283."),
            HumanMessage(content="Reply with only that reference number, without any tool calls.")])
        results["multi_turn"] = response.content.strip() == "49283"
        image = Image.new("RGB", (256, 128), "red")
        image.paste(Image.new("RGB", (128, 128), "blue"), (128, 0))
        data = BytesIO()
        image.save(data, "PNG")
        uri = "data:image/png;base64," + base64.b64encode(data.getvalue()).decode()
        response = await model.with_structured_output(Colors).ainvoke([HumanMessage(content=[
            {"type": "text", "text": "Name the left-half and right-half colors in lowercase English."},
            {"type": "image_url", "image_url": {"url": uri}},
        ])])
        results["image"] = response.left == "red" and response.right == "blue"
    except Exception as error:
        results["error_type"] = type(error).__name__
    return {"provider": model.provider, "checks": results,
            "inference_contract_passed": all(results.get(k) is True for k in (
                "text", "json_schema", "tool_calls", "tool_result_roundtrip", "multi_turn", "image")),
            "android_e2e": "not_checked", "windows_process_cleanup": "not_checked"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-cli", action="store_true")
    parser.add_argument("--ai-cli", choices=("codex", "claude", "gemini", "antigravity"),
                        help="Invoking AI CLI. Required when more than one CLI is installed.")
    parser.add_argument("--output", type=Path, default=Path("traces/local-cli-acceptance.json"))
    args = parser.parse_args()
    if not args.allow_live_cli:
        parser.error("Pass --allow-live-cli to authorize real AI CLI inference on this machine")
    with runtime_settings(provider=args.ai_cli):
        report = asyncio.run(verify())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps(report, indent=2))
    return 0 if report["inference_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
