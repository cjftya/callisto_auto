"""Lossless role/tool history plus explicit, ordered local image attachments."""

import base64
import hashlib
import json
from pathlib import Path

from callisto.llm_adapter.errors import UnsupportedCapability, CLIProtocolError
from callisto.llm_adapter.image_policy import prepare_image

MAX_IMAGE_BYTES = 20_000_000
MAX_PROMPT_BYTES = 8_000_000
MAX_IMAGES = 64
MAX_TOTAL_IMAGE_BYTES = 64_000_000


def encode_messages(messages, directory: Path, *, policy="balanced", metrics=None, include_tool_status=False, compact_text=False):
    history, images = [], []
    attachments = {}
    image_metrics = []
    role_counts = {}
    role_assets = {}
    exposures = []
    seen_assets = set()
    role_transfers = {}
    role_bytes = {}
    shared_references = {}
    evidence_assets = {}
    compact_saved = 0
    loop_exposures = []
    known_evidence_references = 0
    observation = next((m.additional_kwargs.get("callisto_observation_id") for m in messages
                        if m.additional_kwargs.get("callisto_region") == "O"), None)
    references = 0
    total_image_bytes = 0
    transmitted_bytes = 0
    for message in messages:
        content = message.content
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        encoded = []
        geometries = []
        image_ordinal = 0
        for block in blocks:
            if isinstance(block, str):
                encoded.append({"type": "text", "text": block})
                continue
            kind = block.get("type")
            if kind in ("text", "thinking", "reasoning"):
                encoded.append(block)
            elif kind in ("image_url", "image"):
                value = block.get("image_url", block.get("url", ""))
                url = value.get("url", "") if isinstance(value, dict) else value
                if kind == "image" and block.get("source_type") == "base64":
                    url = f"data:{block.get('mime_type', 'image/png')};base64,{block['data']}"
                if not isinstance(url, str) or not url.startswith("data:image/") or ";base64," not in url:
                    raise UnsupportedCapability("Only inline base64 images are supported; remote URLs are not fetched")
                header, data = url.split(",", 1)
                if len(data) > MAX_IMAGE_BYTES * 4 // 3 + 4:
                    raise CLIProtocolError("Image input exceeded the size limit")
                mime = header[5:].split(";", 1)[0]
                suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime)
                if suffix is None:
                    raise UnsupportedCapability("Unsupported image MIME type")
                try:
                    raw = base64.b64decode(data, validate=True)
                except ValueError:
                    raise CLIProtocolError("Malformed base64 image") from None
                total_image_bytes += len(raw)
                references += 1
                if len(raw) > MAX_IMAGE_BYTES or references > MAX_IMAGES or total_image_bytes > MAX_TOTAL_IMAGE_BYTES:
                    raise CLIProtocolError("Image attachments exceeded the request size/count limit; no images were dropped")
                asset_digest = hashlib.sha256(raw).digest()
                role = message.additional_kwargs.get("callisto_image_role", "unknown")
                if role not in ("current", "comparison", "recalled", "historical", "overlay", "unknown"):
                    role = "unknown"
                role_counts[role] = role_counts.get(role, 0) + 1
                role_assets.setdefault(role, set()).add(asset_digest)
                if asset_digest not in seen_assets:
                    from callisto.usage import image_exposure
                    exposures.append(image_exposure(asset_digest))
                    seen_assets.add(asset_digest)
                evidence_ids = message.additional_kwargs.get("callisto_evidence_ids", ())
                evidence_id = evidence_ids[image_ordinal] if image_ordinal < len(evidence_ids) else None
                image_ordinal += 1
                if evidence_id:
                    known_evidence_references += 1
                    evidence_assets.setdefault(asset_digest, set()).add(evidence_id)
                prepared = prepare_image(raw, policy)
                geometries.append({"original_size": list(prepared.geometry.original),
                                   "size": list(prepared.geometry.transmitted), "policy": policy})
                digest = (hashlib.sha256(raw).digest(), references if policy == "off" else 0)
                if digest not in attachments:
                    transmitted_bytes += len(prepared.data)
                    if len(prepared.data) > MAX_IMAGE_BYTES or transmitted_bytes > MAX_TOTAL_IMAGE_BYTES:
                        raise CLIProtocolError("Transformed image attachments exceeded the size limit")
                    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[prepared.mime]
                    path = directory / f"image-{len(images) + 1}{suffix}"
                    path.write_bytes(prepared.data)
                    path.chmod(0o600)
                    images.append(str(path))
                    attachments[digest] = len(images)
                    image_metrics.append(prepared.metrics())
                    role_transfers[role] = role_transfers.get(role, 0) + 1
                    role_bytes[role] = role_bytes.get(role, 0) + len(prepared.data)
                    from callisto.usage import request_exposure
                    loop_exposures.append(request_exposure(("image", observation, asset_digest)) if observation else None)
                else:
                    shared_references[role] = shared_references.get(role, 0) + 1
                encoded.append({"type": "image_attachment", "index": attachments[digest],
                                "mime_type": prepared.mime,
                                "original_size": list(prepared.geometry.original),
                                "size": list(prepared.geometry.transmitted),
                                "coordinate_frame": "stored_pixels; normalized 0..1000 unchanged"})
            else:
                raise UnsupportedCapability(f"CLI input block {kind!r} has no validated conversion")
        if geometries:
            message.additional_kwargs["callisto_image_geometry"] = geometries
        wire_content = encoded
        if (compact_text and len(encoded) == 1 and isinstance(encoded[0], dict)
                and set(encoded[0]) == {"type", "text"} and encoded[0]["type"] == "text"
                and isinstance(encoded[0]["text"], str)):
            wire_content = encoded[0]["text"]
            compact_saved += len(json.dumps(encoded, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) - len(json.dumps(wire_content, ensure_ascii=False).encode("utf-8"))
        record = {"role": message.type, "content": wire_content}
        if getattr(message, "name", None):
            record["name"] = message.name
        if getattr(message, "tool_call_id", None):
            record["tool_call_id"] = message.tool_call_id
        if getattr(message, "tool_calls", None):
            record["tool_calls"] = message.tool_calls
        if include_tool_status and message.type == "tool":
            record["status"] = message.status
        history.append(record)
    if metrics is not None:
        metrics.update(image_policy=policy, image_references=references, image_attachments=len(images),
                       image_original_bytes=total_image_bytes, image_bytes=transmitted_bytes,
                       image_pixels=sum(m["size"][0] * m["size"][1] for m in image_metrics),
                       images=image_metrics, image_role_references=role_counts,
                       image_role_unique_assets={role: len(assets) for role, assets in role_assets.items()},
                       image_required_current_assets=len(role_assets.get("current", set())),
                       image_additional_attachments=len(images) - len(role_assets.get("current", set())),
                       image_role_attachments=role_transfers, image_role_attachment_bytes=role_bytes,
                       image_role_shared_references=shared_references,
                       image_unclassified_evidence_references=references - known_evidence_references,
                       image_same_asset_distinct_evidence=sum(max(0, len(ids)-1) for ids in evidence_assets.values()),
                       image_observation_exposure_counts=loop_exposures,
                       compact_text_saved_bytes=compact_saved,
                       unique_images_in_request=len(seen_assets), image_run_exposure_counts=exposures)
    return history, images


def encode_prompt(history, tools, tool_choice, schema):
    # Put the stable tool/response contract before volatile conversation history.
    # New isolated CLI calls can then reuse a longer identical prompt prefix.
    prompt = (
        "You are the model inference port for ARTEMIS. Complete the supplied conversation. "
        "Do not execute tools, commands, browse, or control Android yourself. Return requested "
        "tool calls as data for ARTEMIS to execute. Message roles and tool results below are "
        "the agent conversation; preserve their order. Images are attached in numbered order. "
        "Repeated image indices refer to the same attachment at each original message position. "
        "Use the coordinate frame requested by the agent; size is the attachment frame and original_size is the device frame. "
        "Return ONLY JSON matching response_schema. Do not add Markdown fences.\n"
        + json.dumps({"tools": tools, "tool_choice": tool_choice,
                      "response_schema": schema, "messages": history},
                     ensure_ascii=False, separators=(",", ":"))
    )
    if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise CLIProtocolError("Conversation exceeded the CLI input size limit; no history was truncated")
    return prompt
