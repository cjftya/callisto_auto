# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import base64
from typing import Any

import httpx
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)
async def perform_ocr(
    screenshot_b64: str,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """Return the existing OCR text/vertex contract through the CLI image port.

    Optional ``client`` is retained for compatibility; no HTTP request is made.
    OCR is opt-in until its image accuracy is validated on the target machine.
    """
    if not is_ocr_configured():
        return []
    from callisto.llm_adapter.model import configured_model
    from callisto.ocr import OCRResult
    from langchain_core.messages import HumanMessage
    from callisto.llm_adapter.image_policy import prepare_image
    from callisto.llm_adapter.errors import CLIProtocolError
    from callisto.settings import effective_settings
    try:
        raw = base64.b64decode(screenshot_b64, validate=True)
    except ValueError:
        raise CLIProtocolError("Malformed base64 OCR input") from None
    geometry = prepare_image(raw, effective_settings().image_policy).geometry
    response = await configured_model().with_structured_output(OCRResult).ainvoke([
        HumanMessage(content=[
            {"type": "text", "text": "Read visible text in this screenshot. Return separate text regions with polygon vertices in transmitted attachment pixel coordinates (size), not original_size. Callisto maps vertices back to device pixels. Do not invent unreadable text."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + screenshot_b64}},
        ])
    ])
    regions = [region.model_dump() for region in response.regions]
    for region in regions:
        for vertex in region["position"]:
            x, y = geometry.original_point(vertex["x"], vertex["y"])
            vertex.update(x=round(x), y=round(y))
    return regions


def is_ocr_configured() -> bool:
    """CLI OCR is explicit opt-in, never enabled by old API key variables."""
    return os.environ.get("CALLISTO_OCR") == "1"
