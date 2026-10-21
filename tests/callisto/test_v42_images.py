"""Inference boundary regressions; never call a real provider or Android."""
import base64
from io import BytesIO
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from PIL import Image
import pytest

from callisto.llm_adapter.codec import encode_messages
from callisto.llm_adapter.errors import CLIProtocolError
from callisto.llm_adapter.image_policy import ImageGeometry, prepare_image
from callisto.usage import collect_usage, usage_summary


def image_bytes(size=(1080, 2400), mode="RGB", fmt="PNG", **kwargs):
    output = BytesIO()
    Image.new(mode, size, 0).save(output, format=fmt, **kwargs)
    return output.getvalue()


def block(raw, mime="image/jpeg"):
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64," + base64.b64encode(raw).decode()}}


@pytest.mark.parametrize("preset,limit", [("balanced", 1920), ("quality", 2560), ("economy", 1440), ("off", 9000)])
@pytest.mark.parametrize("size", [(1080,2400), (2400,1080), (1812,2176), (2176,1812), (720,8000), (1,32)])
def test_dimensions_and_coordinate_roundtrip(preset, limit, size):
    raw = image_bytes(size)
    prepared = prepare_image(raw, preset)
    assert max(prepared.geometry.transmitted) <= min(max(size), limit)
    assert prepared.geometry.original == size
    for nx, ny in [(0,0), (1,1), (0.5,0.8)]:
        w, h = prepared.geometry.transmitted
        x, y = prepared.geometry.original_point(nx*w, ny*h)
        assert (x, y) == pytest.approx((nx*size[0], ny*size[1]))
    assert raw == image_bytes(size)


@pytest.mark.parametrize("fmt,mode", [("PNG","RGBA"), ("JPEG","RGB"), ("WEBP","RGBA"), ("JPEG","CMYK"), ("PNG","P")])
def test_actual_format_alpha_colors_and_rotation(fmt, mode):
    raw = image_bytes((64,128), mode, fmt)
    prepared = prepare_image(raw)
    with Image.open(BytesIO(prepared.data)) as image:
        assert image.format == "JPEG" and image.mode == "RGB"
        if mode == "RGBA":
            assert image.getpixel((0,0)) == (255,255,255)
    assert prepared.original_mime == {"PNG":"image/png", "JPEG":"image/jpeg", "WEBP":"image/webp"}[fmt]


@pytest.mark.parametrize("policy", ["off", "balanced"])
@pytest.mark.parametrize("orientation", range(2,9))
def test_exif_is_removed_without_rotating_coordinate_frame(policy, orientation):
    exif = Image.Exif()
    exif[274] = orientation
    raw = image_bytes((120,60), fmt="JPEG", exif=exif)
    prepared = prepare_image(raw, policy)
    with Image.open(BytesIO(prepared.data)) as image:
        assert image.size == (120,60)
        assert image.getexif().get(274,1) == 1


def test_mime_correction_duplicate_attachment_references_and_tool_order(tmp_path):
    raw = image_bytes((48,96))
    messages = [HumanMessage(content=[block(raw)]), AIMessage(content="", tool_calls=[{"id":"x", "name":"inspect", "args":{}}]),
                ToolMessage(content="observed", tool_call_id="x"), HumanMessage(content=[block(raw)])]
    metrics = {}
    records, paths = encode_messages(messages, tmp_path, metrics=metrics)
    assert len(paths) == 1 and metrics["image_references"] == 2
    assert records[0]["content"][0]["index"] == records[3]["content"][0]["index"] == 1
    assert records[2]["tool_call_id"] == records[1]["tool_calls"][0]["id"]
    assert records[0]["content"][0]["mime_type"] == "image/jpeg"
    assert metrics["images"][0]["original_mime"] == "image/png"
    assert len(encode_messages(messages,tmp_path,policy="off")[1]) == 2
    assert messages[0].content[0] == block(raw)


@pytest.mark.parametrize("raw", [b"not an image", b"\x89PNG\r\n\x1a\n", b"", b"GIF89a"])
def test_corrupt_images_are_never_silently_omitted(raw, tmp_path):
    with pytest.raises(CLIProtocolError):
        encode_messages([HumanMessage(content=[block(raw)])], tmp_path)


def test_base64_count_size_and_pixel_bounds(tmp_path, monkeypatch):
    from callisto.llm_adapter import codec, image_policy
    raw = image_bytes((20,20))
    with pytest.raises(CLIProtocolError, match="Malformed base64"):
        encode_messages([HumanMessage(content=[{"type":"image_url","image_url":{"url":"data:image/png;base64,???"}}])],tmp_path)
    assert len(encode_messages([HumanMessage(content=[block(raw)]*64)],tmp_path)[1]) == 1
    with pytest.raises(CLIProtocolError,match="size/count"):
        encode_messages([HumanMessage(content=[block(raw)]*65)],tmp_path)
    monkeypatch.setattr(codec,"MAX_TOTAL_IMAGE_BYTES",len(raw)*2-1)
    with pytest.raises(CLIProtocolError,match="size/count"):
        encode_messages([HumanMessage(content=[block(raw)]*2)],tmp_path,policy="off")
    monkeypatch.setattr(image_policy,"MAX_PIXELS",10)
    with pytest.raises(CLIProtocolError,match="pixel/memory"):
        prepare_image(image_bytes((7,9)))
    with pytest.raises(CLIProtocolError):
        ImageGeometry((200,300),(100,150)).original_point(-1,0)


@pytest.mark.asyncio
async def test_usage_records_images_failure_unknown_and_cached_subset(monkeypatch):
    from callisto.llm_adapter.model import CLIChatModel
    from tests.callisto.test_adapter import fake_inference, cli_result, envelope
    fake_inference(monkeypatch,cli_result(envelope()))
    with collect_usage() as calls:
        response = await CLIChatModel().ainvoke([HumanMessage(content=[block(image_bytes((16,16)))])])
        assert response.response_metadata["image_metrics"]["image_attachments"] == 1
        with pytest.raises(CLIProtocolError):
            await CLIChatModel().ainvoke([HumanMessage(content=[block(b"bad")])])
    assert len(calls) == 2 and calls[-1]["status"] == "failed"
    assert usage_summary(calls)["input_tokens"] is None
    summary = usage_summary([{ "status":"completed", "cli_usage":{"input_tokens":100,"cached_input_tokens":80,"output_tokens":5}}])
    assert summary["input_tokens"] == 100
    assert summary["cached_input_tokens"] == 80
    assert "base64" not in json.dumps(calls) and "data:image" not in json.dumps(calls)


@pytest.mark.asyncio
async def test_ocr_rescales_pixels_and_rejects_out_of_frame(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from artemis.utils.ocr_api import perform_ocr
    from callisto.ocr import OCRResult
    monkeypatch.setenv("CALLISTO_OCR", "1")
    monkeypatch.setenv("CALLISTO_IMAGE_POLICY", "balanced")
    screenshot = base64.b64encode(image_bytes((1080,2400))).decode()
    fake = MagicMock()
    inference = AsyncMock(return_value=OCRResult(regions=[{"text":"small text", "position":[{"x":432,"y":960},{"x":864,"y":1920}]}]))
    fake.with_structured_output.return_value.ainvoke = inference
    monkeypatch.setattr("callisto.llm_adapter.model.configured_model",lambda:fake)
    assert (await perform_ocr(screenshot))[0]["position"] == [{"x":540,"y":1200},{"x":1080,"y":2400}]
    inference.return_value = OCRResult(regions=[{"text":"bad", "position":[{"x":865,"y":1920},{"x":0,"y":0}]}])
    with pytest.raises(CLIProtocolError,match="outside"):
        await perform_ocr(screenshot)

def test_prompt_reuses_static_protocol_prefix_across_changing_turns():
    """Tool declarations/response schema precede the volatile transcript."""
    from callisto.llm_adapter.codec import encode_prompt

    tools = [{"type": "function", "function": {
        "name": "click", "description": "Tap target", "parameters": {"type": "object"}}}]
    schema = {"type": "object", "properties": {"content": {"type": "string"}}}
    first_history = [{"role": "human", "content": [{"type": "text", "text": "step A"}]}]
    second_history = [{"role": "human", "content": [{"type": "text", "text": "step B"}]}]
    first = encode_prompt(first_history, tools, "auto", schema)
    second = encode_prompt(second_history, tools, "auto", schema)
    marker = '"messages":'
    assert first != second
    assert first[:first.index(marker)] == second[:second.index(marker)]
    body = json.loads(first[first.index("{"):])
    assert list(body) == ["tools", "tool_choice", "response_schema", "messages"]
    assert body["messages"] == first_history
    assert body["tools"] == tools
    assert body["response_schema"] == schema
