"""Content-free per-run usage; cached input is never added to input totals."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
from pathlib import Path

_CURRENT = ContextVar("callisto_usage", default=None)
AGENTS = {"planner", "operator", "explorer", "checker", "validator", "diagnoser", "summarizer",
          "history_analyzer", "outputter", "log_analyzer", "planner_avatar", "planner_validation",
          "validator_pixel_safety_net", "operator_summarizer", "log_reader_sub_agent",
          "diagnoser_expert", "history_analyzer_expert"}
AGENTS.update({"ocr", "object_detector", "image_processor", "hopper", "video_analyzer"})


def agent_label(manager):
    metadata = getattr(manager, "metadata", None) or {}
    value = metadata.get("callisto_agent", metadata.get("langgraph_node"))
    return value if value in AGENTS else "unknown"


def stage_label(manager):
    value = (getattr(manager, "metadata", None) or {}).get("callisto_stage")
    return value if value in ("primary", "fallback") else "unknown"


def record_call(data):
    collector = _CURRENT.get()
    if collector is not None:
        collector.append(data)


@contextmanager
def collect_usage():
    records = []
    token = _CURRENT.set(records)
    try:
        yield records
    finally:
        _CURRENT.reset(token)


def usage_summary(records):
    result = {"calls": len(records), "failed_calls": sum(r["status"] != "completed" for r in records)}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
        values = [r.get("cli_usage", {}).get(key) for r in records]
        result[key] = sum(values) if values and all(v is not None for v in values) else None
        result[f"known_{key}"] = sum(v for v in values if v is not None)
    for key in ("image_attachments", "image_references", "image_pixels", "image_bytes", "image_original_bytes", "elapsed_seconds"):
        result[key] = sum(r.get(key, 0) for r in records)
    result["unknown_usage_calls"] = sum(not r.get("cli_usage") for r in records)
    return result


def write_usage(path: Path, records):
    summary = usage_summary(records)
    groups = {}
    stages = {}
    for r in records:
        groups.setdefault(r["agent"], []).append(r)
        stages.setdefault(r.get("stage", "unknown"), []).append(r)
    payload = {"summary": summary, "by_agent": {k: usage_summary(v) for k, v in groups.items()},
               "by_stage": {k: usage_summary(v) for k, v in stages.items()}, "calls": records}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    path.chmod(0o600)
    return summary
