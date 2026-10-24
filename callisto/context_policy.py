"""Conservative, reversible completed-prefix views over the canonical ledger.

A view never freezes/deletes canonical turns or starts a summary job. Original
hard-pressure compression remains owned by HistoryChunkManager. Off is default.
"""
from dataclasses import dataclass
from pathlib import Path
import time

from langchain_core.messages import HumanMessage

from callisto.llm_adapter.codec import encode_messages
from callisto.llm_adapter.context_ir import closed_transactions
from callisto.llm_adapter.prompt_metrics import json_bytes


@dataclass(frozen=True)
class PolicyDecision:
    messages: tuple
    replaced_turns: int = 0
    saved_text_bytes: int = 0
    blocked_reason: str | None = None
    ready_age_ms: float | None = None

    def metrics(self):
        return dict(replaced_turns=self.replaced_turns, saved_serialized_text_bytes=self.saved_text_bytes,
                    blocked_reason=self.blocked_reason, ready_age_ms=self.ready_age_ms,
                    actual_saved_tokens=None, canonical_mutated=False)


def has_images(messages):
    return any(isinstance(m.content, list) and any(isinstance(b, dict) and
               b.get("type") in ("image", "image_url") for b in m.content) for m in messages)


def text_wire_bytes(messages, *, include_tool_status=False):
    # Caller guarantees imageless source. No files are written by this codec path.
    if has_images(messages):
        raise ValueError("text-only measurement received an image")
    return json_bytes(encode_messages(messages, Path("."), include_tool_status=include_tool_status)[0])


def ready_prefix_view(ledger, manager, baseline, tail):
    from artemis.memory.chunking import render_chunk_block, validate_interval_coverage
    # Ephemeral notices can carry active recovery/incident guidance. Without a
    # structural completion signal, conservatively retain all original history.
    if any(m.additional_kwargs.get("ephemeral_blocks") for m in tail):
        return PolicyDecision(tuple(baseline), blocked_reason="current_ephemeral_guidance")
    all_turns = ledger.unchunked_turns()
    eligible = max(0, len(all_turns) - manager.min_active_turns)
    selected, replacements, consumed, saved = [], [], 0, 0
    reason, ages = None, []
    for entry in manager.ready_policy_entries():
        chunk, turns = entry["chunk"], entry["turns"]
        if chunk is None or chunk.status != "ready":
            reason = "summary_" + entry.get("summary_state", "unknown")
            break
        if not turns or consumed + len(turns) > eligible or turns != all_turns[consumed:consumed+len(turns)]:
            reason = "recent_floor_or_nonprefix"
            break
        keys = [str(k) for t in turns for k in (t.get("step_keys") or [t.get("step_key")]) if k]
        if (not keys or set(keys) != set(chunk.source_step_ids) or not chunk.band3 or
                not validate_interval_coverage(chunk.band1.get("intervals"), chunk.start_step_number, chunk.end_step_number)):
            reason = "coverage_unverified"
            break
        source = [m for t in turns for m in ledger.messages_for_turn(t)]
        registry = getattr(ledger, "evidence_registry", None)
        if registry is not None and any(registry.entries[k].pins for m in source
                for k in m.additional_kwargs.get("callisto_evidence_ids", ()) if k in registry.entries):
            reason = "pinned_evidence"
            break
        if has_images(source):
            reason = "pixel_evidence_retained"
            break
        if not closed_transactions(source):
            reason = "open_tool_transaction"
            break
        if any(getattr(m, "status", None) == "error" or
               (isinstance(m.content, str) and "Not executed:" in m.content) for m in source):
            reason = "error_or_unexecuted_evidence"
            break
        replacement = HumanMessage(content=[{"type": "text", "text": render_chunk_block(chunk)}],
                                   additional_kwargs={"callisto_region": "H"})
        with_status = manager.context_policy == "ready_only"
        benefit = text_wire_bytes(source, include_tool_status=with_status) - text_wire_bytes([replacement])
        if benefit <= 0:
            reason = "no_byte_benefit"
            break
        selected.extend(source)
        replacements.append(replacement)
        consumed += len(turns)
        saved += benefit
        if getattr(chunk, "ready_at", None) is not None:
            ages.append(max(0, (time.monotonic() - chunk.ready_at) * 1000))
    if not selected:
        return PolicyDecision(tuple(baseline), blocked_reason=reason)
    # Identity matching, not equality or string search: only the selected prefix.
    start = next((i for i, m in enumerate(baseline) if m is selected[0]), None)
    if start is None or [id(m) for m in baseline[start:start+len(selected)]] != [id(m) for m in selected]:
        return PolicyDecision(tuple(baseline), blocked_reason="canonical_span_mismatch")
    view = [*baseline[:start], *replacements, *baseline[start+len(selected):]]
    return PolicyDecision(tuple(view), consumed, saved, reason, max(ages) if ages else None)
