from dataclasses import FrozenInstanceError
import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from callisto.llm_adapter.context_ir import ContextIR, closed_transactions
from callisto.context_policy import ready_prefix_view
from tests.unit.memory.test_history_chunking import _make, _step, _turn


def ready_ledger():
    ledger, manager, engine, service = _make([_step(i) for i in range(1, 10)],
        min_active=5, target_tokens=100, auto_capsule=True, meter=lambda: 22000)
    ledger.set_static_prefix([SystemMessage(content="GOAL and user constraints")])
    for i in range(1, 10):
        turn = _turn(i)
        turn[1].content = "FACT must be preserved in canonical history " * 300
        ledger.stage_turn(turn)
        ledger.commit_staged(step_key=f"s{i}")
        manager.on_step_stamped(f"s{i}", "same")
    return ledger, manager


def test_ir_immutable_and_status_tool_pairing():
    messages = [AIMessage(content="", tool_calls=[dict(id="c", name="inspect", args={})]),
                ToolMessage(content="success sounding words", tool_call_id="c", status="error")]
    ir = ContextIR.from_messages(messages)
    assert ir.items[-1].tool_status == "error" and not ir.unresolved_calls
    assert ir.metrics()["error_tool_results"] == 1
    with pytest.raises(FrozenInstanceError):
        ir.items[0].role = "human"
    messages[1].content = "changed"
    assert ir != ContextIR.from_messages(messages)
    assert closed_transactions(messages)
    assert not closed_transactions(messages[:1])
    assert not closed_transactions(messages[::-1])
    assert not closed_transactions(messages + messages)


def test_shadow_keeps_identical_wire_messages_and_canonical_floor():
    ledger, manager = ready_ledger()
    baseline = ledger.render([HumanMessage(content="CURRENT")])
    before = [(m.type, m.content, getattr(m, "tool_calls", None), getattr(m, "tool_call_id", None)) for m in baseline]
    manager.context_policy = "shadow"
    shadow = ledger.render([HumanMessage(content="CURRENT")])
    after = [(m.type, m.content, getattr(m, "tool_calls", None), getattr(m, "tool_call_id", None)) for m in shadow]
    assert before == after
    assert ledger.last_context_policy_metrics["replaced_turns"] > 0
    assert ledger.last_context_policy_metrics["saved_serialized_text_bytes"] > 0
    assert ledger._active_start == 0 and ledger._chunked_turn_count == 0
    assert len(ledger.unchunked_turns()) == 9
    assert ledger.last_context_policy_metrics["canonical_mutated"] is False


def test_pending_prefix_and_invalid_coverage_never_select_later_ready():
    ledger, manager = ready_ledger()
    baseline = ledger.render([])
    first = manager._awaiting[0]["chunk"]
    first.status = "pending"
    assert ready_prefix_view(ledger, manager, baseline, []).replaced_turns == 0
    first.status = "ready"
    first.band1["intervals"] = []
    assert ready_prefix_view(ledger, manager, baseline, []).blocked_reason == "coverage_unverified"


@pytest.mark.parametrize("blocker", ["error", "unexecuted", "unpaired", "image", "notice", "large_capsule"])
def test_safe_view_blocks_protected_or_unprofitable_prefix(blocker):
    ledger, manager = ready_ledger()
    baseline = ledger.render([])
    entry = manager._awaiting[0]
    source = ledger.messages_for_turn(entry["turns"][0])
    tail = []
    if blocker == "error":
        source[-1].status = "error"
    elif blocker == "unexecuted":
        source[-1].content = "Not executed: action deferred"
    elif blocker == "unpaired":
        source[-1].tool_call_id = "different"
    elif blocker == "image":
        source[0].content.append({"type": "image_url", "image_url": {"url": "inline fixture"}})
    elif blocker == "notice":
        tail = [HumanMessage(content="incident", additional_kwargs={"ephemeral_blocks": [0]})]
    else:
        entry["chunk"].band2 = "very large capsule " * 50000
    decision = ready_prefix_view(ledger, manager, baseline, tail)
    assert decision.replaced_turns == 0
    assert decision.messages == tuple(baseline)
