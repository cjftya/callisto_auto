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

"""Repository-wide pytest fixtures and classification helpers.

The default test paths contain only deterministic tests.  Tests under the
integration and end-to-end trees remain directly runnable, and receive stable
markers here so callers can select them without relying on filename patterns.
"""

from pathlib import Path
import os

import pytest

from artemis.drivers.mock.mock_driver import MockDeviceDriver


@pytest.fixture(autouse=True)
def forbid_live_ai_cli(monkeypatch):
    """All automated tests are offline; actual AI CLI execution is prohibited."""
    monkeypatch.setenv("CALLISTO_FORBID_LIVE_CLI", "1")
    # Host proxy configuration must not affect deterministic offline fixtures.
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def mock_driver():
    """Provide an isolated mock mobile driver."""
    return MockDeviceDriver(device_id="fixture-mock-device", width=1080, height=2400)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Attach test-layer markers according to the owning test directory."""
    for item in items:
        parts = Path(str(item.path)).parts
        if "integration" in parts:
            item.add_marker(pytest.mark.integration)
        if "e2e" in parts:
            item.add_marker(pytest.mark.e2e)
    # Some managed Work executors expose host /proc alongside a different PID
    # namespace. A lookup of os.getpid() then probes an unrelated host process.
    # These original tests explicitly need a matching real process view; keep
    # them enabled on normal hosts/CI rather than weakening production locks.
    try:
        mismatched_procfs = os.name == "posix" and int(os.readlink("/proc/self")) != os.getpid()
    except (OSError, ValueError):
        mismatched_procfs = False
    process_view_tests = {
        "test_overlapping_clients_share_one_android_reference",
        "test_migration_cleanup_never_drains_a_live_legacy_owner",
        "test_device_lock_blocks_a_second_process_owner",
        "test_same_serial_on_different_adb_endpoints_has_independent_locks",
        "test_cleanup_stale_locks_keeps_live_owner",
        "test_device_lock_waits_and_runs_next_owner_in_fifo_order",
        "test_submission_reservations_preserve_order_before_workers_start",
        "test_pending_reservation_is_served_with_original_fifo_position_after_claim",
        "test_waiting_acquire_can_be_cancelled_without_leaving_a_ticket",
        "test_active_owner_is_discoverable_and_can_be_annotated",
        "test_multi_device_locks_can_run_concurrently",
        "test_global_concurrency_serial_mode_blocks_other_devices",
        "test_device_pool_list_devices_and_busy_status",
        "test_get_claimed_serials_reflects_locks_and_reservations",
        "test_own_pid_is_alive",
        "test_own_pid_with_matching_create_time_is_alive",
        "test_recycled_pid_with_mismatched_create_time_is_dead",
    }
    if mismatched_procfs:
        for item in items:
            if item.name in process_view_tests:
                item.add_marker(pytest.mark.skip(reason="Host /proc does not match this executor's PID namespace; run on target host/CI"))
