"""Offline scripted context replay; byte effects, NOT model quality or token savings.

Run with CALLISTO_FORBID_LIVE_CLI=1. Only a generated Python fixture child runs.
The meter is an explicitly synthetic gate stimulus, never measured usage.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from PIL import Image

from artemis.memory.chunking import HistoryChunkManager, StepCapsuleLens
from artemis.memory.step_memory import StepMemoryService
from artemis.memory.transcript import TranscriptLedger
from callisto.llm_adapter.codec import encode_messages, encode_prompt
from callisto.llm_adapter.model import response_schema
from callisto.llm_adapter.process import run_process
from callisto.llm_adapter.providers import decode_result
from callisto.llm_adapter.prompt_metrics import json_bytes


class FixtureEngine:
    session_start_time = 1000.0
    current_session_id = "offline-fixture"
    current_step_id = None

    def __init__(self):
        self.steps = []

    def get_agent_friendly_steps(self):
        return self.steps

    def record_history_chunk(self, **kwargs):
        pass

    def record_trace(self, **kwargs):
        pass


def capsule(payload):
    return dict(doing="Read fixture values", did="Recorded fixture actions", effect="Values recorded",
                entry_state="Fixture list", exit_state="Fixture list", verified_facts=["Fixture values are synthetic"],
                unresolved=[], failed_paths=[], important_entities=["fixture"],
                intervals=[dict(start_step=payload["start_step"], end_step=payload["end_step"],
                                text="Read values and recorded actions; originals remain in step history")])


class FixtureSummaries(StepMemoryService):
    def __init__(self, state):
        super().__init__(ctx=None)
        self.state = state
        self.payloads = []
        self.summary_prompt_bytes = 0
        self.summary_output_bytes = 0

    def submit(self, key, payload, aliases=()):
        self._step_inputs[key] = payload
        self.payloads.append(payload)
        # Render the actual capsule prompt with no model invocation.
        messages = StepCapsuleLens(model_name="fixture").build_messages(payload)
        with tempfile.TemporaryDirectory() as directory:
            history, _ = encode_messages(messages, Path(directory))
            self.summary_prompt_bytes += len(encode_prompt(history, [], None, response_schema([])).encode("utf-8"))
        if self.state == "ready":
            self.resolve(key)
        elif self.state == "failed":
            self._failed.add(key)

    def resolve(self, key):
        rendered = json.dumps(capsule(self._step_inputs[key]))
        self._summaries[key] = rendered
        self.summary_output_bytes += len(rendered.encode("utf-8"))

    def advance(self):
        if self.state == "delayed":
            for key in self._step_inputs:
                if key not in self._summaries:
                    self.resolve(key)


def observation(i):
    output = BytesIO()
    Image.new("RGB", (32, 64), (i % 256, 30, 80)).save(output, "PNG")
    url = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
    return HumanMessage(content=[{"type": "text", "text": f"CURRENT-{i}: 한글 UI value {i}; normalized coordinates 0..1000"},
                                 {"type": "image_url", "image_url": {"url": url}}])


FAKE = '''import json,sys
request=json.loads(sys.stdin.read().split("\\n",1)[1])
assert request["messages"]
answer=json.dumps({"content":"fixture accepted","tool_calls":[]})
print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":answer}}))
print(json.dumps({"type":"turn.completed"}))
'''


async def replay(*, start_ratio, loops, steps, summary_state, execute=True, policy="off"):
    engine = FixtureEngine()
    summaries = FixtureSummaries(summary_state)
    visual = StepMemoryService(ctx=None)
    ledger = TranscriptLedger(step_memory=visual, context_budget_tokens=80000, start_ratio=start_ratio,
                              image_scrub_depth=3, image_scrub_depth_relaxed=3, pending_grace_steps=3)
    ledger.set_static_prefix([SystemMessage(content="Preserve goal and constraints. " * 80)])
    config = SimpleNamespace(context_budget_tokens=80000, start_ratio=start_ratio, soft_ratio=.7,
                             hard_ratio=.9, min_active_steps=5, context_policy=policy)
    manager = HistoryChunkManager(engine=engine, transcript_config=config,
                                  chunking_config=SimpleNamespace(min_steps=3, max_steps=12, target_source_tokens=2000),
                                  capsule_service=summaries, meter_getter=lambda: 22000)
    ledger.attach_chunker(manager)
    counters = dict(operator_payload_bytes=0, image_attachments=0, image_references=0,
                    image_attachment_bytes=0, operator_calls=0, fake_process_calls=0, recall_calls=0,
                    transport_retries=0, coverage_checks=0)
    prefixes = []
    policy_saved_bytes = 0
    with tempfile.TemporaryDirectory(prefix="callisto-offline-") as directory:
        directory = Path(directory)
        fake = directory / "fixture.py"
        fake.write_text(FAKE, encoding="utf-8")
        for i in range(1, steps + 1):
            if i % 3 == 0:
                summaries.advance()
            current = observation(i)
            messages = ledger.render([current])
            policy_saved_bytes += ledger.last_context_policy_metrics.get("saved_serialized_text_bytes", 0) * loops
            local_turn = [current]
            for inner in range(loops):
                metrics = {}
                history, images = encode_messages(messages, directory, metrics=metrics, include_tool_status=policy == "ready_only")
                prompt = encode_prompt(history, [], None, response_schema([]))
                # Independent oracle: current image/text and all current-loop pairs survive.
                assert f"CURRENT-{i}:" in prompt
                assert current.content[1] in current.content
                current_record = next(r for r in history if any(
                    b.get("type") == "text" and f"CURRENT-{i}:" in b.get("text", "") for b in r["content"]))
                assert any(b.get("type") == "image_attachment" for b in current_record["content"])
                for j in range(inner):
                    assert f"query-{i}-{j}" in prompt and f"RESULT-{i}-{j}" in prompt
                prefixes.append(prompt.split('"messages":', 1)[0])
                counters["coverage_checks"] += 1
                counters["operator_payload_bytes"] += len(prompt.encode("utf-8"))
                for key in ("image_attachments", "image_references"):
                    counters[key] += metrics[key]
                counters["image_attachment_bytes"] += metrics["image_bytes"]
                counters["operator_calls"] += 1
                if execute:
                    result = await run_process([sys.executable, str(fake)], stdin=prompt, cwd=str(directory), timeout=15)
                    answer, usage = decode_result("codex", result)
                    assert json.loads(answer)["content"] == "fixture accepted" and not usage
                    counters["fake_process_calls"] += 1
                call_id = f"query-{i}-{inner}"
                pair = [AIMessage(content="Read result before action", tool_calls=[dict(id=call_id, name="read_note", args={})]),
                        ToolMessage(content=f"RESULT-{i}-{inner}: " + "preserved 사실 012345 " * 180,
                                    tool_call_id=call_id)]
                messages.extend(pair)
                local_turn.extend(pair)
            ledger.stage_turn(local_turn)
            ledger.commit_staged(step_key=f"s{i}", validator_result={"status": "dispatched"})
            visual._summaries[f"s{i}"] = f"Fixture screen {i}; source s{i} can be recalled"
            engine.steps.append(dict(step_id=f"s{i}", step_number=i, timestamp=1000+i,
                                     summary=f"Fixture screen {i}", action_taken={"action": "wait"},
                                     last_execution_result={"status": "dispatched"}, extra_metadata={}))
            manager.on_step_stamped(f"s{i}", "fixture")
    assert len(set(prefixes)) == 1
    return dict(start_ratio=start_ratio, policy=policy, loops=loops, steps=steps, summary_state=summary_state,
                synthetic_gate_tokens=22000, actual_input_tokens=None, actual_output_tokens=None,
                summary_requests=len(summaries.payloads), summary_prompt_bytes=summaries.summary_prompt_bytes,
                scripted_summary_output_bytes=summaries.summary_output_bytes,
                total_input_payload_bytes=counters["operator_payload_bytes"] + summaries.summary_prompt_bytes,
                swapped_chunks=len(manager.chunks), awaiting_chunks=len(manager.awaiting_chunks),
                stable_tool_prefix=True, candidate_saved_text_bytes=policy_saved_bytes, **counters)


async def compare(execute=True, include_b=False):
    rows = []
    for steps in (4, 16):
        for loops in (1, 2, 4, 8):
            for state in ("ready", "pending", "failed", "delayed"):
                for ratio in (.35, .25, 0.0):
                    rows.append(await replay(start_ratio=ratio, loops=loops, steps=steps,
                                             summary_state=state, execute=execute))
                if include_b:
                    for mode in ("shadow", "ready_only"):
                        rows.append(await replay(start_ratio=.35, loops=loops, steps=steps,
                                                 summary_state=state, execute=execute, policy=mode))
    return {"method": "scripted transport/context replay; not live Operator or model-quality acceptance",
            "actual_tokens": None, "summary_execution": "rendered prompts and scripted capsules; no inference",
            "net_token_savings": None, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-b", action="store_true")
    parser.add_argument("--no-child", action="store_true", help="codec-only replay for quick regression")
    args = parser.parse_args()
    if os.environ.get("CALLISTO_FORBID_LIVE_CLI") != "1":
        parser.error("CALLISTO_FORBID_LIVE_CLI=1 is required")
    report = asyncio.run(compare(execute=not args.no_child, include_b=args.include_b))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(report['rows'])} offline comparisons to {args.output}")


if __name__ == "__main__":
    main()
