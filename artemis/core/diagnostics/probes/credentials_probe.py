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

"""CLI installation readiness; authentication is owned by the official CLI."""
import os
import shutil
from artemis.core.diagnostics.probes.base import BaseProbe
from artemis.core.diagnostics.schema import ProbeCategory, ProbeResult, ProbeStatus

class LLMCredentialsProbe(BaseProbe):
    @property
    def probe_id(self):
        # Keep the historical identifier for stored readiness report compatibility.
        return "gemini_api_key"

    @property
    def category(self):
        return ProbeCategory.CREDENTIALS

    @property
    def is_blocker(self):
        return True

    async def probe(self):
        provider = os.environ.get("CALLISTO_AI_CLI", "codex")
        executable = os.environ.get(f"CALLISTO_{provider.upper()}_EXECUTABLE", provider)
        installed = bool(shutil.which(executable))
        available = installed and provider in ("codex", "claude")
        return ProbeResult(id=self.probe_id, category=self.category, title="AI CLI installation",
            status=ProbeStatus.PASS if available else ProbeStatus.FAIL, is_blocker=True,
            summary="Installed (login unverified)" if available else "CLI unavailable",
            description="Uses official CLI login; no API keys are inspected or returned. Run real inference acceptance on the target PC.",
            metadata={"provider": provider, "installed": installed, "configured_count": int(available),
                      "authentication": "not_checked", "inference": "not_checked"})

class VisionOCRProbe(BaseProbe):
    @property
    def probe_id(self):
        return "vision_ocr_key"

    @property
    def category(self):
        return ProbeCategory.CREDENTIALS

    @property
    def is_blocker(self):
        return False

    async def probe(self):
        from artemis.utils.ocr_api import is_ocr_configured
        enabled = is_ocr_configured()
        return ProbeResult(id=self.probe_id, category=self.category, title="Optional CLI OCR",
            status=ProbeStatus.PASS, is_blocker=False,
            summary="Enabled (unverified)" if enabled else "Disabled (optional)",
            description="OCR uses the CLI image port when CALLISTO_OCR=1. Local Helper/XML perception remains available.",
            metadata={"enabled": enabled, "configured": enabled, "transport": "cli", "accuracy": "not_checked"})
