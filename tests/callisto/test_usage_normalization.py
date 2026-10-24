import asyncio
import json

import pytest
from langchain_core.messages import HumanMessage

from callisto.llm_adapter.usage_normalization import normalize_usage
from callisto.llm_adapter.model import CLIChatModel
from callisto.usage import collect_usage, usage_summary
from tests.callisto.test_adapter import fake_inference, cli_result, envelope


def test_codex_cache_is_subset_and_null_is_not_zero():
    n = normalize_usage("codex", {"input_tokens": 100, "cached_input_tokens": 80, "output_tokens": 5}, scope="request")
    assert n["logical_input_tokens"] == 100
    assert n["uncached_input_tokens"] == 20
    assert n["cache_write_tokens"] is None
    assert n["context_input_tokens"] == 100
    assert normalize_usage("codex", {"input_tokens": True})["logical_input_tokens"] is None


def test_claude_complete_partial_and_aggregated_usage():
    raw = {"input_tokens": 10, "cache_read_input_tokens": 70, "cache_creation_input_tokens": 20, "output_tokens": 6}
    n = normalize_usage("claude", raw, scope="invocation")
    assert n["logical_input_tokens"] == 100 and n["context_input_tokens"] is None
    assert normalize_usage("claude", raw, scope="invocation", context_is_single_request=True)["context_input_tokens"] == 100
    del raw["cache_creation_input_tokens"]
    assert normalize_usage("claude", raw)["logical_input_tokens"] is None
    assert n["raw_usage"]["cache_creation_input_tokens"] == 20


def test_gemini_complete_rows_only_unknown_scope_never_aggregates():
    raw = {"models": {"one": {"tokens": {"prompt": 100, "cached": 30, "thoughts": 8, "response": 20}},
                      "two": {"tokens": {"prompt": 50}}}}
    n = normalize_usage("gemini", raw, scope="invocation")
    assert n["logical_input_tokens"] == 150
    assert n["output_tokens"] is None and n["cache_read_tokens"] is None
    n = normalize_usage("codex", {"input_tokens": 900}, scope="session_cumulative")
    summary = usage_summary([{"status": "completed", "normalized_usage": n}])
    assert summary["normalized_logical_input_tokens"] is None
    assert summary["known_normalized_logical_input_tokens"] == 0
    assert n["context_input_tokens"] is None


@pytest.mark.asyncio
async def test_metrics_bytes_unicode_ids_and_run_isolation(monkeypatch):
    fake_inference(monkeypatch, cli_result(envelope()))
    model = CLIChatModel()
    async def run(run_id):
        with collect_usage(run_id) as calls:
            await model.ainvoke([HumanMessage(content="한글 private-text", additional_kwargs={"callisto_region": "O"})])
            return calls
    a, b = await asyncio.gather(run("a"), run("b"))
    assert a[0]["run_id"] == "a" and b[0]["run_id"] == "b"
    assert a[0]["inference_attempt_id"] != b[0]["inference_attempt_id"]
    assert a[0]["callisto_payload_bytes"] == a[0]["provider_stdin_bytes"]
    assert a[0]["prompt_region_bytes"]["O"] > len("한글 private-text")
    assert a[0]["queue_wait_ms"] >= 0 and a[0]["process_ms"] >= 0
    assert "private-text" not in json.dumps(a)
    assert usage_summary(a)["normalized_logical_input_tokens"] == 12
