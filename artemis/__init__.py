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

"""ARTEMIS Pro runtime preserved by Callisto (Apache-2.0)."""
from artemis._version import __version__
from artemis import _legacy_imports
_legacy_imports.install()

def __getattr__(name):
    import importlib
    exports = {"Agent": ("artemis.sdk.agent", "Agent"), "Builders": ("artemis.sdk.builders", "Builders"),
               "BaseDeviceDriver": ("artemis.drivers.base", "BaseDeviceDriver"),
               "ArtemisClient": ("artemis.interfaces.sdk.client", "ArtemisClient"),
               "ConcurrencyMode": ("artemis.interfaces.sdk.client", "ConcurrencyMode"),
               "Task": ("artemis.interfaces.sdk.task", "Task"),
               "StreamEvent": ("artemis.interfaces.sdk.task", "StreamEvent"),
               "StreamEventType": ("artemis.interfaces.sdk.task", "StreamEventType"),
               **{key: ("artemis_client", key) for key in ("Capabilities", "Device", "TaskHandle", "TaskResult")}}
    if name in exports:
        module, attr = exports[name]
        return getattr(importlib.import_module(module), attr)
    raise AttributeError(name)
