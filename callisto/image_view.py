"""Opt-in historical image transmission view; never edits the canonical ledger."""
import os

from callisto.llm_adapter.context_ir import closed_transactions


def image_view_mode():
    value = os.environ.get("CALLISTO_OPERATOR_IMAGE_POLICY", "off")
    if value not in ("off", "shadow", "ready_only"):
        raise ValueError("CALLISTO_OPERATOR_IMAGE_POLICY must be off, shadow or ready_only")
    return value


def image_view(ledger, messages, *, mode):
    registry = ledger.evidence_registry
    counts = {"mode": mode, "candidate_references": 0, "removed_references": 0, "blocked": {},
              "canonical_mutated": False}
    if ledger._policy_resource_error:
        counts["blocked"]["evidence_capacity"] = 1
        return list(messages), counts
    eligible = set()
    turns = ledger.unchunked_turns()
    floor = max(5, getattr(ledger.chunker, "min_active_turns", 5))
    for turn in turns[:max(0, len(turns) - floor)]:
        source = ledger.messages_for_turn(turn)
        if closed_transactions(source) and not any(getattr(m, "status", None) == "error" for m in source):
            eligible.update(id(m) for m in source)
    output = []
    for message in messages:
        blocks = message.content if isinstance(message.content, list) else []
        images = [b for b in blocks if isinstance(b, dict) and b.get("type") in ("image", "image_url")]
        if not images:
            output.append(message)
            continue
        reason = None
        keys = message.additional_kwargs.get("callisto_evidence_ids", ())
        items = [registry.entries.get(k) for k in keys] if registry else []
        if id(message) not in eligible:
            reason = "current_loop_or_recent_or_unclosed"
        elif ledger._policy_hold_history or any(m.additional_kwargs.get("ephemeral_blocks") for m in messages if m.additional_kwargs.get("callisto_region") == "O"):
            reason = "active_guidance"
        elif len(items) != len(images) or any(e is None for e in items):
            reason = "unknown_identity"
        elif any(e.role != "historical" or e.pins for e in items):
            reason = "role_or_pin"
        elif registry.protect(message, ledger._step_memory):
            reason = "summary_not_ready"
        if reason:
            counts["blocked"][reason] = counts["blocked"].get(reason, 0) + len(images)
            output.append(message)
            continue
        # Require a single exact source summary. Keep every non-image block,
        # message identity, tool ID/status, and positions in the transmission view.
        steps = {e.source_step_id for e in items}
        if len(steps) != 1:
            counts["blocked"]["mixed_sources"] = counts["blocked"].get("mixed_sources", 0) + len(images)
            output.append(message)
            continue
        summary = ledger._step_memory.get_summary(next(iter(steps)))
        counts["candidate_references"] += len(images)
        if mode == "ready_only":
            content = [{"type": "text", "text": "[Historical image summary; original available via get_step_screenshot] " + str(summary)}
                       if isinstance(b, dict) and b.get("type") in ("image", "image_url") else b for b in blocks]
            output.append(message.model_copy(update={"content": content}))
            counts["removed_references"] += len(images)
        else:
            output.append(message)
    return output, counts
