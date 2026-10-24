"""Immutable read-only request IR. Ledger messages remain the canonical context.

The IR contains hashes/counters and transaction/evidence identities, never a second
mutable memory. It is not fed to the model and cannot replace message content.
"""
from dataclasses import dataclass
import hashlib
import json


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContextItem:
    index: int
    role: str
    region: str
    content_fingerprint: str
    tool_call_ids: tuple[str, ...]
    tool_result_id: str | None
    tool_status: str | None
    image_references: int
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ContextIR:
    items: tuple[ContextItem, ...]
    schema_version: str = "context-ir-v1"

    @classmethod
    def from_messages(cls, messages):
        items = []
        seen_observation = False
        for i, msg in enumerate(messages):
            sidecar = msg.additional_kwargs
            region = sidecar.get("callisto_region", "unknown")
            if region == "O":
                seen_observation = True
            elif region == "unknown" and seen_observation:
                region = "R"
            blocks = msg.content if isinstance(msg.content, list) else []
            calls = tuple(str(c["id"]) for c in getattr(msg, "tool_calls", ()) or ())
            items.append(ContextItem(i, msg.type, region,
                fingerprint({"content": msg.content, "calls": getattr(msg, "tool_calls", None),
                             "name": getattr(msg, "name", None)}), calls,
                getattr(msg, "tool_call_id", None), getattr(msg, "status", None),
                sum(isinstance(b, dict) and b.get("type") in ("image", "image_url") for b in blocks),
                tuple(sidecar.get("callisto_evidence_ids", ()))))
        return cls(tuple(items))

    @property
    def unresolved_calls(self):
        calls, results = set(), set()
        for item in self.items:
            calls.update(item.tool_call_ids)
            if item.tool_result_id:
                results.add(item.tool_result_id)
        return tuple(sorted(calls - results))

    def metrics(self):
        return {"context_ir_version": self.schema_version, "context_messages": len(self.items),
                "unresolved_tool_calls": len(self.unresolved_calls),
                "error_tool_results": sum(i.tool_status == "error" for i in self.items),
                "context_image_references": sum(i.image_references for i in self.items)}


def closed_transactions(messages):
    """No orphan/duplicate/out-of-order results may disappear into a capsule."""
    pending, seen = set(), set()
    for msg in messages:
        for call in getattr(msg, "tool_calls", ()) or ():
            key = call.get("id")
            if not key or key in seen:
                return False
            seen.add(key)
            pending.add(key)
        key = getattr(msg, "tool_call_id", None)
        if key:
            if key not in pending:
                return False
            pending.remove(key)
    return not pending
