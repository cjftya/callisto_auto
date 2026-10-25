"""Content-free byte accounting. Sections are serialized bytes, not token estimates."""
import json


def json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def prompt_metrics(messages, history, tools, choice, schema, prompt, stdin):
    regions = dict.fromkeys(("S", "D", "H", "O", "R", "unknown"), 0)
    regions["D"] = json_bytes({"tools": tools, "tool_choice": choice, "response_schema": schema})
    from callisto.llm_adapter.context_ir import fingerprint
    from callisto.usage import request_exposure
    repeated = dict.fromkeys(regions, 0)
    history_kinds = {}
    contract = {"tools": tools, "tool_choice": choice, "response_schema": schema}
    if (request_exposure(("contract", fingerprint(contract))) or 0) > 1:
        repeated["D"] = regions["D"]
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
        size = json_bytes(record)
        regions[region] += size
        if region == "H":
            kind = message.additional_kwargs.get("callisto_history_kind", "unknown")
            if kind not in ("restored", "frozen", "ledger", "capsule"):
                kind = "unknown"
            history_kinds[kind] = history_kinds.get(kind, 0) + size
        if (request_exposure(("text", region, fingerprint(record))) or 0) > 1:
            repeated[region] += size
    return {"callisto_payload_bytes": len(prompt.encode("utf-8")),
            "prompt_history_bytes": history_kinds,
            "prompt_fixed_wrapper_bytes": len(prompt.encode("utf-8")) - json_bytes({**contract, "messages": history}),
            "provider_stdin_bytes": len(stdin.encode("utf-8")),
            "prompt_region_bytes": regions, "prompt_repeated_region_bytes": repeated, "rendered_messages": len(history),
            "actual_input_tokens": None, "byte_accounting_version": "serialized-sections-v1"}
