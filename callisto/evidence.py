"""Run-local image evidence and explicit pin lifetimes; no image content is stored here."""
from dataclasses import dataclass, field
import base64
import hashlib
from uuid import uuid4

from callisto.llm_adapter.errors import CLIProtocolError

ROLES = {"current", "comparison", "recalled", "historical", "overlay", "unknown"}


@dataclass
class ImageEvidence:
    evidence_id: str
    asset_id: str | None
    observation_id: str
    variant: int
    role: str
    source_step_id: str | None
    source_tool_call_id: str | None
    original_bytes: int
    pins: dict[str, str] = field(default_factory=dict)
    decision_released: bool = False
    summary_status: str = "unknown"
    summary_version: int | None = None
    original_geometry: tuple[int, int] | None = None
    transmitted_geometry: tuple[int, int] | None = None
    transform_policy: str | None = None
    coordinate_frame: str = "stored_pixels; normalized 0..1000 unchanged"


class EvidenceRegistry:
    def __init__(self, *, run_id=None, max_pins=32, max_pin_bytes=32_000_000, max_entries=4096):
        self.run_id = str(run_id or uuid4())
        self.entries = {}
        self.max_pins, self.max_pin_bytes, self.max_entries = max_pins, max_pin_bytes, max_entries
        self.lifecycle_counts = {}

    def register(self, message, *, observation_id, role=None, step_id=None):
        blocks = message.content if isinstance(message.content, list) else []
        images = [b for b in blocks if isinstance(b, dict) and b.get("type") in ("image", "image_url")]
        if not images:
            return ()
        identities = []
        for block in images:
            raw = None
            try:
                value = block.get("image_url", block.get("url", ""))
                url = value.get("url", "") if isinstance(value, dict) else value
                data = block.get("data") if block.get("source_type") == "base64" else url.split(";base64,", 1)[1]
                raw = base64.b64decode(data, validate=True)
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                pass  # The codec rejects malformed/remote images at transport.
            asset = hashlib.sha256(raw).hexdigest() + ":original-stored-v1" if raw is not None else None
            identities.append((asset, len(raw) if raw is not None else 0))
        existing = message.additional_kwargs.get("callisto_evidence_ids", ())
        if (len(existing) == len(images) and all(e in self.entries for e in existing)
                and all(self.entries[e].asset_id == asset
                        for e, (asset, _) in zip(existing, identities))):
            self.sync_geometry(message)
            return tuple(existing)
        if len(self.entries) + len(images) > self.max_entries:
            raise CLIProtocolError("Evidence registry capacity exceeded; no evidence was evicted")
        # A changed payload or a resumed sidecar cannot inherit a prior release.
        role = "unknown" if existing else role or message.additional_kwargs.get("callisto_image_role", "unknown")
        role = role if role in ROLES else "unknown"
        ids = []
        for variant, (asset, original_bytes) in enumerate(identities):
            evidence_id = f"{self.run_id}:{uuid4()}"
            item = ImageEvidence(evidence_id, asset, str(observation_id), variant, role,
                                 str(step_id) if step_id is not None else None,
                                 message.additional_kwargs.get("callisto_source_tool_call_id") or getattr(message, "tool_call_id", None),
                                 original_bytes)
            if role in ("recalled", "comparison", "overlay", "unknown"):
                item.pins[role] = f"decision:{observation_id}"
            self.entries[evidence_id] = item
            ids.append(evidence_id)
        message.additional_kwargs["callisto_evidence_ids"] = ids
        message.additional_kwargs["callisto_image_role"] = role
        self.sync_geometry(message)
        return tuple(ids)

    def sync_geometry(self, message):
        geometries = message.additional_kwargs.get("callisto_image_geometry", ())
        for key, geometry in zip(message.additional_kwargs.get("callisto_evidence_ids", ()), geometries):
            item = self.entries.get(key)
            if item is not None:
                item.original_geometry = tuple(geometry["original_size"])
                item.transmitted_geometry = tuple(geometry["size"])
                item.transform_policy = geometry["policy"]

    def mark_historical(self, message, step_id):
        for key in message.additional_kwargs.get("callisto_evidence_ids", ()):
            item = self.entries.get(key)
            if item is not None and item.role == "current":
                item.role = "historical"
                item.source_step_id = str(step_id) if step_id is not None else None
                message.additional_kwargs["callisto_image_role"] = "historical"

    def pin(self, evidence_id, *, reason, until):
        if not reason or not until:
            raise ValueError("Pins require an explicit reason and release event")
        self.entries[evidence_id].pins[str(reason)] = str(until)

    def release(self, event):
        """Only explicit lifecycle events release pins, never image age or bytes."""
        for item in self.entries.values():
            item.pins = {reason: until for reason, until in item.pins.items() if until != event}

    def finish_turn(self, messages, *, step_id, result):
        """Shared ledger commit hook, after the preserved Validator has returned.

        Dispatch closes this turn's decision, not the blocked intent of an
        incident. No timeout, age, model prose or successful helper implies it.
        """
        from callisto.llm_adapter.context_ir import closed_transactions
        keys = {k for m in messages for k in m.additional_kwargs.get("callisto_evidence_ids", ())}
        items = [self.entries[k] for k in keys if k in self.entries]
        status = result.get("status") if isinstance(result, dict) else None
        if status == "failed" and step_id:
            for item in items:
                item.pins[f"incident:{step_id}"] = f"incident:{step_id}"
            outcome = "failed_retained"
        elif (status == "dispatched" and step_id and not result.get("incident")
              and closed_transactions(messages)
              and not any(getattr(m, "status", None) == "error" for m in messages)):
            outcome = "dispatched"
            for item in items:
                # Unknown/overlay/comparison ownership is not established by a
                # screenshot recall. Only release a proven consumed recall.
                carriers = [i for i, m in enumerate(messages)
                            if item.evidence_id in m.additional_kwargs.get("callisto_evidence_ids", ())]
                consumed = (carriers and any(m.type == "ai" for m in messages[max(carriers)+1:])
                            and any(getattr(m, "tool_call_id", None) == item.source_tool_call_id
                                    and getattr(m, "status", None) == "success" for m in messages)
                            and any(c.get("id") == item.source_tool_call_id and c.get("name") == "get_step_screenshot"
                                    for m in messages for c in (getattr(m, "tool_calls", None) or [])))
                if item.role != "recalled" or not consumed or not item.source_tool_call_id:
                    continue
                event = f"decision:{item.observation_id}"
                if item.pins.get("recalled") == event:
                    del item.pins["recalled"]
                    item.decision_released = True
                    item.role = "historical"
                    self.lifecycle_counts["recall_decision_released"] = self.lifecycle_counts.get("recall_decision_released", 0) + 1
        else:
            outcome = "unconfirmed_retained"
        self.lifecycle_counts[outcome] = self.lifecycle_counts.get(outcome, 0) + 1

    def check_limits(self):
        pinned = [e for e in self.entries.values() if e.pins]
        if len(pinned) > self.max_pins or sum(e.original_bytes for e in pinned) > self.max_pin_bytes:
            raise CLIProtocolError("Image pin capacity exceeded; release completed decisions explicitly or restart from DataEngine; no evidence was dropped")

    def protect(self, message, summary_service):
        keys = message.additional_kwargs.get("callisto_evidence_ids", ())
        if not keys:
            return True  # unclassified image cannot be cost-evicted
        protected = False
        for key in keys:
            item = self.entries.get(key)
            if item is None:
                return True
            step = item.source_step_id
            summary = summary_service.get_summary(step) if summary_service is not None and step else None
            if summary:
                item.summary_status, item.summary_version = "ready", 1
            elif summary_service is not None and step and summary_service.has_failed(step):
                item.summary_status = "failed"
            elif summary_service is not None and step and summary_service.is_pending(step):
                item.summary_status = "pending"
            else:
                item.summary_status = "unknown"
            protected |= item.asset_id is None or bool(item.pins) or item.role != "historical" or item.summary_status != "ready"
        return protected

    def metrics(self):
        result = {"evidence_count": len(self.entries), "pinned_evidence": 0, "roles": {}, "summary_status": {}, "lifecycle": dict(self.lifecycle_counts)}
        for item in self.entries.values():
            result["pinned_evidence"] += bool(item.pins)
            result["roles"][item.role] = result["roles"].get(item.role, 0) + 1
            result["summary_status"][item.summary_status] = result["summary_status"].get(item.summary_status, 0) + 1
        return result
