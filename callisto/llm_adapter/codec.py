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


def encode_messages(messages, directory: Path, *, policy="balanced", metrics=None):
    history, images = [], []
    attachments = {}
    image_metrics = []
    references = 0
    total_image_bytes = 0
    transmitted_bytes = 0
    for message in messages:
        content = message.content
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        encoded = []
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
                prepared = prepare_image(raw, policy)
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
                encoded.append({"type": "image_attachment", "index": attachments[digest],
                                "mime_type": prepared.mime,
                                "original_size": list(prepared.geometry.original),
                                "size": list(prepared.geometry.transmitted),
                                "coordinate_frame": "stored_pixels; normalized 0..1000 unchanged"})
            else:
                raise UnsupportedCapability(f"CLI input block {kind!r} has no validated conversion")
        record = {"role": message.type, "content": encoded}
        if getattr(message, "name", None):
            record["name"] = message.name
        if getattr(message, "tool_call_id", None):
            record["tool_call_id"] = message.tool_call_id
        if getattr(message, "tool_calls", None):
            record["tool_calls"] = message.tool_calls
        history.append(record)
    if metrics is not None:
        metrics.update(image_policy=policy, image_references=references, image_attachments=len(images),
                       image_original_bytes=total_image_bytes, image_bytes=transmitted_bytes,
                       image_pixels=sum(m["size"][0] * m["size"][1] for m in image_metrics),
                       images=image_metrics)
    return history, images


def encode_prompt(history, tools, tool_choice, schema):
    prompt = (
        "You are the model inference port for ARTEMIS. Complete the supplied conversation. "
        "Do not execute tools, commands, browse, or control Android yourself. Return requested "
        "tool calls as data for ARTEMIS to execute. Message roles and tool results below are "
        "the agent conversation; preserve their order. Images are attached in numbered order. "
        "Repeated image indices refer to the same attachment at each original message position. "
        "Use the coordinate frame requested by the agent; size is the attachment frame and original_size is the device frame. "
        "Return ONLY JSON matching response_schema. Do not add Markdown fences.\n"
        + json.dumps({"messages": history, "tools": tools, "tool_choice": tool_choice,
                      "response_schema": schema}, ensure_ascii=False)
    )
    if len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise CLIProtocolError("Conversation exceeded the CLI input size limit; no history was truncated")
    return prompt
