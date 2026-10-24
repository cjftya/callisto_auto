import pytest
from langchain_core.messages import HumanMessage, ToolMessage

from callisto.evidence import EvidenceRegistry
from callisto.llm_adapter.codec import encode_messages
from callisto.llm_adapter.errors import CLIProtocolError
from artemis.memory.step_memory import StepMemoryService
from artemis.tools.tool_wrapper import tool_result_messages
from tests.callisto.test_v42_images import image_bytes, block
from tests.callisto.test_ready_context_policy import ready_ledger


def image_message(role="unknown"):
    return HumanMessage(content=[block(image_bytes((16, 24)))], additional_kwargs={"callisto_image_role": role})


def test_asset_identity_does_not_merge_evidence_or_small_pixel_changes():
    registry = EvidenceRegistry(run_id="one")
    a, b = image_message("current"), image_message("recalled")
    ea = registry.register(a, observation_id="obs-a")[0]
    eb = registry.register(b, observation_id="obs-b")[0]
    assert ea != eb and registry.entries[ea].asset_id == registry.entries[eb].asset_id
    assert registry.entries[eb].pins and not registry.entries[ea].pins
    from PIL import Image
    from io import BytesIO
    image = Image.new("RGB", (16, 24))
    image.putpixel((1, 1), (1, 0, 0))
    out = BytesIO()
    image.save(out, "PNG")
    c = HumanMessage(content=[block(out.getvalue())])
    ec = registry.register(c, observation_id="obs-c")[0]
    assert registry.entries[ec].asset_id != registry.entries[ea].asset_id


def test_explicit_lifecycle_does_not_release_incident_with_decision():
    registry = EvidenceRegistry()
    message = image_message("recalled")
    key = registry.register(message, observation_id="obs")[0]
    registry.pin(key, reason="incident", until="incident:resolved")
    registry.release("decision:obs")
    assert registry.entries[key].pins == {"incident": "incident:resolved"}
    registry.release("incident:resolved")
    assert not registry.entries[key].pins
    assert key in registry.entries  # identity/recall provenance retained


def test_caps_are_explicit_no_eviction_and_runs_are_isolated():
    a, b = EvidenceRegistry(max_pins=1), EvidenceRegistry()
    a.register(image_message(), observation_id="1")
    a.register(image_message(), observation_id="2")
    with pytest.raises(CLIProtocolError, match="no evidence was dropped"):
        a.check_limits()
    assert len(a.entries) == 2 and not b.entries
    assert a.run_id != b.run_id


@pytest.mark.parametrize("state", ["ready", "pending", "failed", "unknown"])
def test_historical_only_ready_unpinned_pixels_can_scrub(state):
    registry, memory = EvidenceRegistry(), StepMemoryService(ctx=None)
    message = image_message("current")
    registry.register(message, observation_id="1")
    registry.mark_historical(message, "s1")
    if state == "ready":
        memory._summaries["s1"] = "known pixel summary"
    elif state == "pending":
        memory._step_inputs["s1"] = {}
    elif state == "failed":
        memory._failed.add("s1")
    assert registry.protect(message, memory) is (state != "ready")


@pytest.mark.parametrize("carrier", ["tool", "human"])
def test_recall_provenance_tool_status_and_geometry(carrier, tmp_path):
    messages = tool_result_messages("call-1", [{"type": "text", "text": "Step 7 screenshot"},
                                             block(image_bytes((32, 64)))], name="get_step_screenshot",
                                    status="error", image_carrier=carrier)
    assert messages[-1].additional_kwargs["callisto_source_tool_call_id"] == "call-1"
    assert messages[-1].additional_kwargs["callisto_image_role"] == "recalled"
    records, paths = encode_messages(messages, tmp_path, include_tool_status=True)
    assert records[0]["status"] == "error" and records[0]["tool_call_id"] == "call-1"
    assert len(paths) == 1
    assert next(b for r in records for b in r["content"] if b["type"] == "image_attachment")["original_size"] == [32, 64]
    baseline, _ = encode_messages(messages, tmp_path)
    assert "status" not in baseline[0]


def test_ready_view_toggle_recovers_canonical_history_and_current_pixels():
    ledger, manager = ready_ledger()
    # Establish baseline scrub before enabling the optional view.
    baseline = ledger.render([HumanMessage(content="current")])
    manager.context_policy = "ready_only"
    current = image_message("current")
    view = ledger.render([current])
    assert len(view) < len(baseline)
    assert current in view and current.content[0]["type"] == "image_url"
    assert ledger._active_start == 0 and len(ledger.unchunked_turns()) == 9
    manager.context_policy = "off"
    restored = ledger.render([HumanMessage(content="current")])
    assert [m.content for m in restored] == [m.content for m in baseline]


def test_recalled_image_survives_many_renders_and_blocks_legacy_hard_fold():
    ledger, manager = ready_ledger()
    manager.context_policy = "ready_only"
    # Replace first old image with actual bytes, attach explicit recall provenance.
    message = ledger._active[0]
    message.content = image_message().content
    message.additional_kwargs["callisto_image_role"] = "recalled"
    for _ in range(8):
        ledger.render([image_message("current")])
    assert message.content[0]["type"] == "image_url"
    assert ledger.evidence_registry.metrics()["pinned_evidence"] >= 1
    manager._meter_getter = lambda: 95000
    with pytest.raises(CLIProtocolError, match="Protected evidence"):
        ledger.render([image_message("current")])
    assert message.content[0]["type"] == "image_url" and ledger._active_start == 0


def test_geometry_sidecar_tracks_actual_transport_without_changing_pixels(tmp_path):
    registry = EvidenceRegistry()
    message = HumanMessage(content=[block(image_bytes((200, 400)))])
    key = registry.register(message, observation_id="geometry", role="current")[0]
    original = message.content.copy()
    encode_messages([message], tmp_path)
    registry.sync_geometry(message)
    item = registry.entries[key]
    assert item.original_geometry == (200, 400)
    assert item.transmitted_geometry == (200, 400)
    assert item.transform_policy == "balanced" and message.content == original


@pytest.mark.asyncio
async def test_actual_adapter_shadow_identical_and_optin_carries_status(monkeypatch):
    import json
    from callisto.llm_adapter.model import CLIChatModel
    from tests.callisto.test_adapter import fake_inference, cli_result, envelope
    run = fake_inference(monkeypatch, cli_result(envelope()))
    ledger, manager = ready_ledger()
    for message in ledger._active:
        if isinstance(message.content, list):
            message.content = [block(image_bytes((16, 24))) if b.get("type") == "image_url" else b for b in message.content]
    baseline = ledger.render([HumanMessage(content="CURRENT")])
    await CLIChatModel().ainvoke(baseline)
    original = run.call_args.kwargs["stdin"]
    manager.context_policy = "shadow"
    shadow = ledger.render([HumanMessage(content="CURRENT")])
    await CLIChatModel().ainvoke(shadow)
    assert run.call_args.kwargs["stdin"] == original
    manager.context_policy = "ready_only"
    optin = ledger.render([HumanMessage(content="CURRENT")])
    optin.append(ToolMessage(tool_call_id="error-call", content="Looks successful", status="error"))
    await CLIChatModel().ainvoke(optin)
    wire = json.loads(run.call_args.kwargs["stdin"].split("\n", 1)[1])
    assert wire["messages"][-1]["status"] == "error"
    assert wire["messages"][-1]["tool_call_id"] == "error-call"
    assert len(run.call_args.kwargs["stdin"]) < len(original)


def test_recall_shadow_never_changes_baseline_summary_lookup():
    from artemis.memory.transcript import TranscriptLedger
    from artemis.memory.chunking import HistoryChunkManager
    from types import SimpleNamespace
    from tools.compare_operator_context import FixtureEngine, FixtureSummaries
    def make(mode):
        engine = FixtureEngine()
        engine.steps = [{"step_id": "source", "step_number": 7}]
        memory = StepMemoryService(ctx=None)
        memory._summaries["source"] = "RECALL-SUMMARY-MUST-NOT-LEAK-IN-SHADOW"
        ledger = TranscriptLedger(step_memory=memory)
        ledger.attach_chunker(HistoryChunkManager(engine=engine,
            transcript_config=SimpleNamespace(context_policy=mode), capsule_service=FixtureSummaries("pending")))
        ledger.stage_turn(tool_result_messages("lookup", [{"type": "text", "text": "Step 7 screenshot"},
            block(image_bytes((16, 24)))], name="get_step_screenshot", image_carrier="human"))
        ledger.commit_staged()
        return ledger
    off, shadow = make("off"), make("shadow")
    for i in range(5):
        a, b = off.render([image_message("current")]), shadow.render([image_message("current")])
        assert [m.content for m in a] == [m.content for m in b]
        for ledger in (off, shadow):
            ledger.stage_turn([image_message("current")])
            ledger.commit_staged(step_key=f"s{i}")
