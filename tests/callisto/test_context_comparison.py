import pytest
from tools.compare_operator_context import replay


@pytest.mark.asyncio
async def test_short_task_has_no_capsule_effect():
    a = await replay(start_ratio=.35, loops=2, steps=4, summary_state="ready", execute=False)
    b = await replay(start_ratio=0, loops=2, steps=4, summary_state="ready", execute=False)
    assert a["operator_payload_bytes"] == b["operator_payload_bytes"]
    assert a["image_attachments"] == b["image_attachments"]
    assert a["summary_requests"] == b["summary_requests"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["ready", "pending", "failed", "delayed"])
async def test_gate_effect_is_ready_only_and_has_no_extra_summary_calls(state):
    a = await replay(start_ratio=.35, loops=1, steps=16, summary_state=state, execute=False)
    b = await replay(start_ratio=.25, loops=1, steps=16, summary_state=state, execute=False)
    assert a["summary_requests"] == b["summary_requests"]
    assert a["image_attachments"] == b["image_attachments"]
    if state in ("ready", "delayed"):
        assert b["operator_payload_bytes"] < a["operator_payload_bytes"]
    else:
        assert b["operator_payload_bytes"] == a["operator_payload_bytes"]
    assert a["actual_input_tokens"] is b["actual_input_tokens"] is None
