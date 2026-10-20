# DataEngine / Setup followup — 2026-10-21

## Baseline and scope

Clean remote/local `main` was `95316612b04c8c5ee096c6e74e526b12739f716c`.
Implementation is prepared on local branch `fix/data-engine-followup`; no remote
publication, `main` merge or new-commit CI is claimed.

Changes are limited to storage-thread synchronization, Setup success guidance,
related tests, Windows regression selection and current documentation.
Antigravity inference stays `UNSUPPORTED`; explicit hosts do not fall back.
No live AI CLI, login, user Skill repair, Android operation or Helper rebuild ran.

## Reproduction and implementation

A controlled `Thread.start()` gate held the storage thread between registration
and actual start. On the unchanged baseline, a snapshot-and-join reproduced
`RuntimeError: cannot join thread before it is started`, while
`has_pending_operations()` incorrectly returned `False`.

Three deterministic regression cases failed before the implementation:

| Controlled observation | Baseline failure | Fixed result |
| --- | --- | --- |
| Pending check while start is paused | `False` although a write was registered | Waits for start and reports pending |
| Shutdown while start is paused | Returns before SQLite device-info update (`{}`) | Returns after persisted `{"saved": true}` |
| Parent schedules a child after shutdown takes its first snapshot | Shutdown returns with child still blocked | Waits for child and its real Trace write |

Events and an observed real lock enforce the ordering, without sleeps or retries.
The same three tests pass after the engine fix. Eight lifecycle cases also cover
fast completion (100 submissions), start failure cleanup/propagation, logged
storage errors, 16 concurrent submissions and the existing asyncio-task path.

`_pending_threads_lock` protects registration/start, removal and snapshots.
Failed starts unregister before propagating the error. Fast workers cannot
finish cleanup before registration. `_wait_for_pending_threads()` joins outside
the lock and rechecks for descendant storage work; shutdown uses the same drain
off the event loop. Fourteen unsafe test snapshot/join loops across five existing
files now use that shared method.

The drain assumes unrelated producers have been quiesced by the caller. It does
not close admission, drain a separate logging queue, or add a timeout/cancellation
policy; an unending producer or blocked storage operation remains outside this
limited lifecycle fix. No joins or awaits run with the storage-thread lock held.

Setup changes only `READY` guidance: names come from `ready_providers`, for
example `Ask Codex to test Android with Callisto.` or
`Ask Codex or Claude Code to test Android with Callisto.` Unready/unsupported
hosts remain in their existing diagnostics. Action/unsupported advice, JSON
fields, selection, Skill/Helper operations and exit codes 0/1/2 are retained.

## Preservation policy

`artemis/data_engine/engine.py` is outside both immutable preservation manifests.
The authorized exception is limited to the lifecycle methods described above;
[upstream baseline](../upstream-baseline.md) records the reason. All **32 + 23**
original hashes match without changing either manifest. Pro graphs/prompts,
CLI/image/coordinate adapters, storage models/schema and Helper artifacts have
no diff. The async-task creation and exception callback are unchanged. Existing
history, offline-reader, step-summary and agent-history regressions pass.

## Verification

Linux Work executor, Python 3.12.14, `CALLISTO_FORBID_LIVE_CLI=1`:

- Focused DataEngine/history/Setup/Doctor regression: **218 passed**.
- Lifecycle stress: **20 repetitions × 8 cases = 160 passed**. This supplements
  the deterministic failing-before/passing-after evidence above.
- Full `python -m pytest -q -ra`: **2358 passed, 4 failed, 31 skipped,
  8 deselected**, 72.02 seconds. The full suite is **not green** in this executor.
- The four failures are unchanged `test_uninstall.py` subprocess cases:
  `test_external_worker_deletes_only_temporary_install[system/venv/native]` and
  `test_shell_launcher_dry_run`. They report `ACTION_REQUIRED: Stop Callisto/setup
  processes and retry`. The executor exposes a different PID namespace from
  `/proc` (observed Python PID 6 vs `/proc/self` 11398), so the safety inventory
  treats the launcher itself as another busy process. A separate untouched
  worktree at baseline `95316612b0` reproduces the same **4 failed, 2 skipped,
  38 deselected** result for those worker/launcher selections. Neither removal
  safety nor skip rules were modified to conceal these failures.
- Existing skips: 7 Windows/PowerShell-only cases, 4 unavailable Android/ADB
  cases, 17 PID/procfs-dependent cases, 2 opt-in live SDK-role cases and 1 missing
  history-analyzer fixture. Eight default marker deselections remain unchanged.
- Ruff over `callisto tools tests/callisto` and all changed engine/unit files:
  passed. `pip check`, frontend-free wheel build and `git diff --check`: passed.
- `tools/verify_wheel.py --require-helper` passed in a clean venv outside the
  checkout: dependency check, Pro/config/SDK imports, CLI help, temporary Skill
  install/update/status and the bundled Helper APK/manifest verification.
  This is packaging evidence, not official-host Skill recognition or device E2E.
- Existing warnings include Pillow `getdata()` deprecation, runpy re-imports and
  mocked Google SDK thinking levels; no new thread-exception warning occurred.

## CI and remaining acceptance

[Actions 39454988484](https://github.com/cjftya/callisto_auto/actions/runs/39454988484)
was verified successful at the baseline SHA: Windows/Linux CLI regression and
Windows/Linux Helper build jobs all passed. Opposite-OS conditional steps were
skipped as configured; Windows runs its portability subset and Linux the full
offline suite. Both earlier commits `4524496` and `95316612b0` are already in
remote `main`; the earlier pending-publication report is corrected accordingly.

That run predates this fix. New-commit Windows/Linux CI has **not run**, because
the work is prepared locally pending a separate publication instruction. The
Windows CI selection now explicitly includes the new lifecycle regression file;
Linux already collects it. Normal-host uninstall verification, official CLI
inference and Android acceptance remain separate, unexecuted checks.
