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
from typing import Any

import httpx
from artemis.config import settings
from third_party.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)
_HTTP_CLIENT: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.AsyncClient(timeout=30.0)
    return _HTTP_CLIENT


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
    response = await configured_model().with_structured_output(OCRResult).ainvoke([
        HumanMessage(content=[
            {"type": "text", "text": "Read visible text in this screenshot. Return separate text regions with polygon vertices in original image pixel coordinates. Do not invent unreadable text."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + screenshot_b64}},
        ])
    ])
    return [region.model_dump() for region in response.regions]


def _parse_ocr_response(response: httpx.Response) -> list[dict[str, Any]]:
    if response.status_code == 200:
        res_json = response.json()
        responses = res_json.get("responses", [])
        if responses and "textAnnotations" in responses[0]:
            annotations = responses[0]["textAnnotations"]
            results = []
            # Skip the first annotation (index 0) as it is the full-screen combined text
            for ann in annotations[1:]:
                desc = ann.get("description", "")
                vertices = ann.get("boundingPoly", {}).get("vertices", [])
                results.append({"text": desc, "position": vertices})
            return results
        else:
            return []
    else:
        raise Exception(f"Vision API returned status {response.status_code}: {response.text}")


def is_ocr_configured() -> bool:
    """CLI OCR is explicit opt-in, never enabled by old API key variables."""
    return os.environ.get("CALLISTO_OCR") == "1"
