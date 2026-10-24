"""Safety oracles for transmission-only candidates and terminal evidence ownership."""
import copy
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from artemis.memory.transcript import TranscriptLedger
from artemis.memory.step_memory import StepMemoryService
from artemis.tools.tool_wrapper import tool_result_messages
from callisto.evidence import EvidenceRegistry
from callisto.image_view import image_view
from callisto.llm_adapter.codec import encode_messages, encode_prompt
from callisto.llm_adapter.errors import CLIProtocolError
from callisto.llm_adapter.model import response_schema
from callisto.llm_adapter.prompt_metrics import prompt_metrics
from callisto.usage import collect_usage, usage_summary
from tests.callisto.test_evidence_policy import image_message
from tests.callisto.test_v42_images import image_bytes, block


def recall_turn(*, error=False, consumed=True, carrier="human"):
    messages = [AIMessage(content="look", tool_calls=[dict(id="recall", name="get_step_screenshot", args={})])]
    messages += tool_result_messages("recall", [block(image_bytes((16, 24)))],
                                     name="get_step_screenshot", status="error" if error else "success",
                                     image_carrier=carrier)
    if consumed:
        messages += [AIMessage(content="observed", tool_calls=[dict(id="act", name="tap", args={})]),
                     ToolMessage(content="Action Recorded", tool_call_id="act")]
    return messages


@pytest.mark.parametrize("carrier", ["human", "tool"])
def test_ledger_committed_consumed_recall_releases_only_decision(carrier):
    ledger = TranscriptLedger()
    ledger.evidence_registry = EvidenceRegistry()
    ledger._observation_id = "obs"
    messages = recall_turn(carrier=carrier)
    ledger.stage_turn(messages)
    registry = ledger.evidence_registry
    item = next(iter(registry.entries.values()))
    registry.pin(item.evidence_id, reason="comparison", until="comparison:explicit-owner")
    ledger.commit_staged(step_key="s1", validator_result={"status": "dispatched", "incident": None})
    assert item.decision_released and item.role == "historical"
    assert item.pins == {"comparison": "comparison:explicit-owner"}
    assert all(m in ledger.active_messages for m in messages)
    ledger.release_evidence("unrelated")
    assert item.pins
    ledger.release_evidence("comparison:explicit-owner")
    assert not item.pins


@pytest.mark.parametrize("failure", ["error", "unconsumed", "missing_result", "cancel", "timeout", "failed", "open_pair", "duplicate", "incident", "no_step", "unknown", "comparison"])
def test_uncertain_lifecycles_retain_pins(failure):
    registry = EvidenceRegistry()
    messages = recall_turn(error=failure == "error", consumed=failure != "unconsumed")
    if failure == "open_pair":
        messages.pop()
    if failure == "duplicate":
        messages.append(messages[-1])
    if failure in ("unknown", "comparison"):
        for message in messages:
            if "callisto_image_role" in message.additional_kwargs:
                message.additional_kwargs["callisto_image_role"] = failure
    for message in messages:
        registry.register(message, observation_id="o")
    result = {"status": "dispatched", "incident": None}
    if failure in ("missing_result", "cancel", "timeout"):
        result = None
    if failure == "failed":
        result = {"status": "failed"}
    if failure == "incident":
        result["incident"] = {"kind": "exec_error"}
    registry.finish_turn(messages, step_id=None if failure == "no_step" else "s1", result=result)
    assert all(e.pins and not e.decision_released for e in registry.entries.values())


def test_repeated_incidents_never_release_when_only_dispatch_channel_recovers():
    registry = EvidenceRegistry()
    messages = recall_turn()
    for message in messages:
        registry.register(message, observation_id="o")
    for i in range(3):
        registry.finish_turn(messages, step_id=f"s{i}", result={"status": "failed"})
    registry.finish_turn(messages, step_id="s4", result={"status": "dispatched"})
    item = next(iter(registry.entries.values()))
    assert set(item.pins) == {"incident:s0", "incident:s1", "incident:s2"}
    registry.release("incident:s1")
    assert set(item.pins) == {"incident:s0", "incident:s2"}


def test_caps_long_run_and_restart_preserve_uncertain_ownership():
    registry = EvidenceRegistry(max_entries=4096)
    for i in range(100):
        messages = recall_turn()
        for message in messages:
            registry.register(message, observation_id=str(i))
        registry.finish_turn(messages, step_id=str(i), result={"status": "dispatched"})
        registry.check_limits()
    assert not any(e.pins for e in registry.entries.values())
    restored = EvidenceRegistry()
    for message in messages:
        restored.register(message, observation_id="restart")
    assert all(e.pins for e in restored.entries.values())
    bounded = EvidenceRegistry(max_pins=32, max_pin_bytes=32_000_000)
    for i in range(32):
        bounded.register(image_message(), observation_id=str(i))
    bounded.check_limits()
    bounded.register(image_message(), observation_id="33")
    with pytest.raises(CLIProtocolError):
        bounded.check_limits()
    assert len(bounded.entries) == 33
    one = next(iter(bounded.entries.values()))
    one.original_bytes = 32_000_001
    bounded.max_pins = 100
    with pytest.raises(CLIProtocolError):
        bounded.check_limits()
    full = EvidenceRegistry(max_entries=4096)
    for i in range(4096):
        full.register(image_message("current"), observation_id=str(i))
    with pytest.raises(CLIProtocolError):
        full.register(image_message(), observation_id="overflow")
    assert len(full.entries) == 4096


def view_ledger():
    ledger = TranscriptLedger(step_memory=StepMemoryService(ctx=None))
    ledger.evidence_registry = EvidenceRegistry()
    for i in range(7):
        message = image_message("current")
        ledger.evidence_registry.register(message, observation_id=str(i))
        ledger.stage_turn([message])
        ledger.commit_staged(step_key=f"s{i}")
        ledger._step_memory._summaries[f"s{i}"] = f"screen {i}, text 123, checked box"
    current = image_message("current")
    return ledger, [*ledger.active_messages, current]


@pytest.mark.parametrize("blocker", [None, "pin", "unknown", "recalled", "comparison", "overlay", "pending", "failed", "missing", "guidance", "unclassified"])
def test_image_candidate_changes_only_safe_old_transmission(blocker):
    ledger, messages = view_ledger()
    registry = ledger.evidence_registry
    item = next(iter(registry.entries.values()))
    if blocker == "pin":
        registry.pin(item.evidence_id, reason="incident", until="incident:done")
    elif blocker in ("unknown", "recalled", "comparison", "overlay"):
        item.role = blocker
    elif blocker in ("pending", "failed", "missing"):
        ledger._step_memory._summaries.pop("s0")
        if blocker == "pending":
            ledger._step_memory._step_inputs["s0"] = {}
        elif blocker == "failed":
            ledger._step_memory._failed.add("s0")
    elif blocker == "guidance":
        messages[-1].additional_kwargs.update(callisto_region="O", ephemeral_blocks=[0])
    elif blocker == "unclassified":
        messages[0].additional_kwargs.pop("callisto_evidence_ids")
    before = copy.deepcopy([m.content for m in messages])
    shadow, counts = image_view(ledger, messages, mode="shadow")
    assert all(a is b for a, b in zip(messages, shadow))
    candidate, actual = image_view(ledger, messages, mode="ready_only")
    assert [m.content for m in messages] == before
    assert candidate[-1] is messages[-1]
    assert all(a is b for a, b in zip(candidate[2:], messages[2:]))
    assert actual["removed_references"] == counts["candidate_references"]
    assert (candidate[0] is not messages[0]) is (blocker is None)


def test_compact_codec_lossless_metadata_and_status(tmp_path):
    messages = [HumanMessage(content="한글 unicode"), ToolMessage(content="fine", tool_call_id="c", status="error"),
                HumanMessage(content=[{"type": "text", "text": "preserve", "cache_control": {"type": "ephemeral"}}]),
                image_message("current")]
    before = copy.deepcopy([m.content for m in messages])
    old, paths = encode_messages(messages, tmp_path, include_tool_status=True)
    metrics = {}
    new, paths2 = encode_messages(messages, tmp_path, include_tool_status=True, compact_text=True, metrics=metrics)
    for a, b in zip(old, new):
        expanded = dict(b)
        if isinstance(b["content"], str):
            expanded["content"] = [{"type": "text", "text": b["content"]}]
        assert expanded == a
    assert new[1]["status"] == "error" and new[1]["tool_call_id"] == "c"
    assert metrics["compact_text_saved_bytes"] == 50 and paths == paths2
    assert [m.content for m in messages] == before


def test_role_byte_accounting_and_loop_repetition_no_hashes(tmp_path):
    a, b = image_message("current"), image_message("recalled")
    a.additional_kwargs.update(callisto_region="O", callisto_observation_id="obs")
    registry = EvidenceRegistry()
    registry.register(a, observation_id="obs")
    registry.register(b, observation_id="obs")
    with collect_usage():
        for iteration in (1, 2):
            metrics = {}
            history, paths = encode_messages([a, b], tmp_path, metrics=metrics)
            assert len(paths) == 1
            assert sum(metrics["image_role_attachment_bytes"].values()) == metrics["image_bytes"]
            assert metrics["image_role_shared_references"] == {"recalled": 1}
            assert metrics["image_same_asset_distinct_evidence"] == 1
            assert metrics["image_observation_exposure_counts"] == [iteration]
            prompt = encode_prompt(history, [], None, response_schema([]))
            measured = prompt_metrics([a, b], history, [], None, response_schema([]), prompt, prompt)
            assert bool(measured["prompt_repeated_region_bytes"]["O"]) is (iteration == 2)
            assert all(e.asset_id not in json.dumps(metrics) for e in registry.entries.values())


def test_mixed_provider_normalized_totals_are_not_comparable():
    records = [dict(status="completed", provider=p, normalized_usage={"usage_scope": "request", "logical_input_tokens": 10})
               for p in ("codex", "claude")]
    result = usage_summary(records)
    assert result["mixed_providers"] and result["normalized_logical_input_tokens"] is None
    assert result["known_normalized_logical_input_tokens"] is None


def test_acceptance_requires_version_scope_and_human_quality_review():
    from tools.compare_operator_acceptance import compare
    meta = dict(provider="codex", cli_version="fixture", model_settings_label="same", scenario_revision="v1", device_configuration_label="synthetic")
    def run(tokens, review=True):
        return {"one/01": {"result": {"test_status": "passed"}, "calls": [dict(provider="codex", agent="operator", status="completed",
                normalized_usage={"usage_scope": "invocation", "uncached_input_tokens": tokens})],
                "review": dict(task_success=True, false_pass=False, evidence_missing=False, unsafe_release=False) if review else {}}}
    assert compare((meta, run(100)), (meta, run(80)))["median_uncached_reduction_percent"] == pytest.approx(20)
    assert compare((meta, run(100)), (meta, run(80, False)))["median_uncached_reduction_percent"] is None
    assert compare((meta, run(100)), ({**meta, "cli_version": "other"}, run(80)))["median_uncached_reduction_percent"] is None
    broken = run(80)
    broken["one/01"]["calls"][0]["normalized_usage"]["usage_scope"] = "session_cumulative"
    assert compare((meta, run(100)), (meta, broken))["median_uncached_reduction_percent"] is None
    broken["one/01"]["review"]["false_pass"] = True
    assert compare((meta, run(100)), (meta, broken))["stop_and_rollback_samples"] == ["one/01"]


@pytest.mark.asyncio
async def test_v2_replay_baseline_and_shadow_are_identical():
    from tools.compare_operator_context import replay
    options = dict(start_ratio=.35, loops=2, steps=4, summary_state="ready", execute=False, policy="ready_only")
    a = await replay(**options)
    b = await replay(**options, image_mode="shadow")
    c = await replay(**options, image_mode="ready_only", compact_text=True)
    assert a["operator_payload_bytes"] == b["operator_payload_bytes"]
    assert a["image_attachments"] == b["image_attachments"] == c["image_attachments"]
    assert c["operator_payload_bytes"] < a["operator_payload_bytes"]
    assert c["actual_input_tokens"] is None
    assert sum(a["image_role_attachments"].values()) == a["image_attachments"]


@pytest.mark.asyncio
async def test_candidate_fake_child_transport_never_fabricates_usage():
    from tools.compare_operator_context import replay
    result = await replay(start_ratio=.35, loops=2, steps=4, summary_state="ready", execute=True,
                          policy="ready_only", image_mode="ready_only", compact_text=True)
    assert result["fake_process_calls"] == 8
    assert result["actual_input_tokens"] is None and result["actual_output_tokens"] is None


@pytest.mark.parametrize("size", [(240, 120), (120, 240), (64, 96)])
def test_current_small_text_checkbox_pixels_survive_view(size, tmp_path):
    from io import BytesIO
    from PIL import Image, ImageDraw
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.text((2, 2), "10 / 01 / 99", fill="black")
    draw.rectangle((2, 20, 10, 28), outline="black")
    draw.line((3, 24, 6, 27, 9, 21), fill="black")
    stream = BytesIO()
    image.save(stream, "PNG")
    ledger, messages = view_ledger()
    current = HumanMessage(content=[block(stream.getvalue())], additional_kwargs={"callisto_image_role": "current"})
    messages[-1] = current
    candidate, _ = image_view(ledger, messages, mode="ready_only")
    assert candidate[-1] is current
    wire, paths = encode_messages([current], tmp_path, policy="off")
    with Image.open(paths[0]) as transmitted:
        assert transmitted.size == size and transmitted.tobytes() == image.tobytes()
    assert wire[0]["content"][0]["original_size"] == list(size)


def test_changed_pixels_cannot_inherit_completed_evidence_identity():
    registry = EvidenceRegistry()
    message = image_message("historical")
    old = registry.register(message, observation_id="old", step_id="s1")[0]
    message.content = [block(image_bytes((31, 23)))]
    new = registry.register(message, observation_id="new", step_id="s1")[0]
    assert old != new
    assert registry.entries[new].role == "unknown" and registry.entries[new].pins
    memory = StepMemoryService(ctx=None)
    memory._summaries["s1"] = "ready"
    assert registry.protect(message, memory)


def test_unknown_role_stays_protected_even_after_explicit_pin_release():
    registry = EvidenceRegistry()
    message = image_message("unknown")
    registry.register(message, observation_id="o", step_id="s1")
    memory = StepMemoryService(ctx=None)
    memory._summaries["s1"] = "ready"
    registry.release("decision:o")
    assert registry.protect(message, memory)


def test_failed_recovery_is_excluded_from_cost_success_pairs():
    from tools.compare_operator_acceptance import compare
    meta = dict(provider="codex", cli_version="fixture", model_settings_label="same", scenario_revision="v1", device_configuration_label="synthetic")
    sample = {"result": {}, "calls": [dict(provider="codex", status="completed", agent="operator",
              normalized_usage={"usage_scope": "request", "uncached_input_tokens": 100})],
              "review": dict(task_success=True, false_pass=False, evidence_missing=False, unsafe_release=False, recovery_success=False)}
    result = compare((meta, {"one": sample}), (meta, {"one": sample}))
    assert result["measured_successful_pairs"] == 0 and result["stop_and_rollback_samples"] == ["one"]


@pytest.mark.asyncio
async def test_environment_switches_reach_actual_adapter(monkeypatch):
    from tests.callisto.test_adapter import fake_inference, cli_result, envelope
    from callisto.llm_adapter.model import CLIChatModel
    run = fake_inference(monkeypatch, cli_result(envelope()))
    ledger = TranscriptLedger()
    current = image_message("current")
    messages = ledger.render([current])
    messages.append(ToolMessage(content="result text", tool_call_id="c", status="error"))
    await CLIChatModel().ainvoke(messages)
    original = run.call_args.kwargs["stdin"]
    monkeypatch.setenv("CALLISTO_OPERATOR_IMAGE_POLICY", "shadow")
    messages = ledger.render([current])
    messages.append(ToolMessage(content="result text", tool_call_id="c", status="error"))
    with collect_usage() as calls:
        await CLIChatModel().ainvoke(messages)
    assert run.call_args.kwargs["stdin"] == original
    assert calls[0]["context_policy"]["image_view"]["mode"] == "shadow"
    monkeypatch.setenv("CALLISTO_COMPACT_TEXT", "1")
    await CLIChatModel().ainvoke(messages)
    wire = json.loads(run.call_args.kwargs["stdin"].split("\n", 1)[1])
    assert wire["messages"][-1]["content"] == "result text"
    assert wire["messages"][-1]["status"] == "error"
    monkeypatch.setenv("CALLISTO_COMPACT_TEXT", "0")
    monkeypatch.setenv("CALLISTO_OPERATOR_IMAGE_POLICY", "off")
    messages = ledger.render([current])
    messages.append(ToolMessage(content="result text", tool_call_id="c", status="error"))
    await CLIChatModel().ainvoke(messages)
    assert run.call_args.kwargs["stdin"] == original


def test_current_observation_wins_over_reused_historical_object():
    ledger, messages = view_ledger()
    current = messages[0]
    current.additional_kwargs.update(callisto_region="O", callisto_image_role="current")
    # Simulate a host reusing a prior message object as the new observation.
    messages[-1] = current
    candidate, counts = image_view(ledger, messages, mode="ready_only")
    assert candidate[0] is current and candidate[-1] is current
    assert counts["blocked"]["current_observation_or_loop"] == 2
