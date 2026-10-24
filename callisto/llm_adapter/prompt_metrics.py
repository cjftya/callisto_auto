"""Content-free byte accounting. Sections are serialized bytes, not token estimates."""
import json


def json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def prompt_metrics(messages, history, tools, choice, schema, prompt, stdin):
    regions = dict.fromkeys(("S", "D", "H", "O", "R", "unknown"), 0)
    regions["D"] = json_bytes({"tools": tools, "tool_choice": choice, "response_schema": schema})
    seen_observation = False
    for message, record in zip(messages, history):
        region = message.additional_kwargs.get("callisto_region", "unknown")
        if region == "O":
            seen_observation = True
        elif region == "unknown" and seen_observation:
            region = "R"
        if region not in regions or region == "D":
            region = "unknown"
        if message.type == "system":
            region = "S"
        regions[region] += json_bytes(record)
    return {"callisto_payload_bytes": len(prompt.encode("utf-8")),
            "provider_stdin_bytes": len(stdin.encode("utf-8")),
            "prompt_region_bytes": regions, "rendered_messages": len(history),
            "actual_input_tokens": None, "byte_accounting_version": "serialized-sections-v1"}
