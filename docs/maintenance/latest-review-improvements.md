# Latest review improvements — 2026-10-21

## Baseline and scope

Local `main` and remote `main` both resolved to
`a850b907cf873e443949aa51f0ea4145259aa0ca` before editing; the worktree was clean.
The baseline [Windows/Linux workflow](https://github.com/cjftya/callisto_auto/actions/runs/39448603724)
completed successfully. This report covers plan A; the separate Antigravity
transport gate is recorded in [Antigravity integration](antigravity-integration.md).

## Changes and compatibility

- `callisto/setup.py`: each host retains installed/launcher status plus
  `inference_supported`, `ready`, and `issues`. Existing `clis`, `skills`,
  `authentications` and single-host aliases remain. `ready_providers`,
  `unsupported_hosts`, and `warnings` are additive. In auto mode one ready
  supported host suffices; failures of other hosts become warnings. Python
  dependencies, ADB/device selection and Helper failures remain global blockers.
  Existing Skill repair, authentication probes and Helper behavior are preserved.
- `callisto/cli.py`: existing boolean `clis` entries remain; additive `hosts`
  carry per-host details. `cli_installed`/`launcher_supported` now mean at least
  one launchable detected host; `provider_implemented` means at least one
  implemented provider. Actual readiness requires a launchable implemented host
  in `ready_providers`, valid transport configuration and an ADB path. Doctor
  still runs no provider CLI and checks no authentication, Skill or device.
- Both commands expose `status`: `READY` exits 0, `ACTION_REQUIRED` exits 1,
  Antigravity-only or explicit Antigravity `UNSUPPORTED` exits 2. Doctor's
  unsupported exit changes from 1 to 2. Explicit hosts never fall back.
  `READY` is preparation evidence, not model/Android acceptance.
- `README.md`: manual removal includes all four host directories and preserves
  modified/foreign Skills, CLI authentication, IDE Skills and device Helper.
  The remover already covers all four paths; no removal logic was changed and
  no actual user installation was removed.
- `scripts/setup.ps1`: retained because the architecture and prior cleanup
  report identify an externally callable compatibility path. It now warns and
  delegates to root `setup.ps1` by script location, forwarding supported flags
  and exit codes. Legacy `-Python` is explicitly rejected before installation;
  root Python selection is unchanged. Root `setup.ps1` / `setup.sh` are the
  documented official entrypoints. Bootstrap itself is unchanged.

Repository search found no CI or executable caller of `scripts/setup.ps1`;
the prior architecture and `cleanup-report.md` record explain why it was retained.
No public import, default model, transport, Pro graph/prompt, image/coordinate
policy, dependency/configuration file, preservation manifest, or Helper artifact
was changed. The two immutable preservation manifests remain the test oracle.

## Validation

Normal Windows host, Python 3.13.15, `CALLISTO_FORBID_LIVE_CLI=1`.
The sandbox could not access the existing Android SDK at import time; tests were
therefore run on the normal host without weakening the runtime or process checks.

- Final focused tests: **70 passed, 1 skipped** (POSIX shell unavailable).
  The table covers single/mixed/all/absent hosts, all/broken launchers, explicit
  selection, login and Skill failures, ADB/unauthorized/Helper/dependency errors,
  Doctor configuration errors, and unsupported inference before any child or
  Android launch. The wrapper runs against an inert temporary root installer
  from a different working directory, checking flags and exit propagation.
- First full suite: **2363 passed, 10 skipped, 8 deselected**. The later final
  suite included four additional Doctor/wrapper cases and reported **2363
  passed, 1 failed, 3 errors, 10 skipped, 8 deselected**; all four failures were
  the unchanged history fixture synchronization issue below. These failures
  are retained as evidence, not excluded or moved.
- Final full rerun after dependency installation completed: **2367 passed,
  10 skipped, 8 deselected** in 184.60 seconds. No tests or engine code were
  changed between the intermittent failure and this successful rerun.
- `python -m ruff check callisto tools tests/callisto`, `python -m pip check`,
  frontend-free wheel build, and `git diff --check`: passed.
- All **32 + 23** immutable preservation hashes match. Protected `artemis/`,
  configuration, dependency declarations, `.gitattributes`, Helper source/APK
  and manifests have no diff. All edited text files retain LF bytes.
- Final wheel runtime modules match the source byte for byte. Bundled Helper
  APK SHA-256 remains
  `73590b206d576abd24beb0d35aee2657b6bd65af1e060db188e0a5de3365d6ec`.
  Both the initial and final rebuilt wheel passed clean-venv
  `tools/verify_wheel.py --require-helper`, including pip check, Pro imports,
  CLI help, canonical Skill lifecycle and Helper APK/manifest validation.
- Active README/AGENTS/canonical Skill/top-level documentation local targets:
  **42 checked, 0 missing** before the separate Antigravity report update.
- Skips: POSIX process assertion (1), Linux uninstall launcher (1), absent POSIX
  setup shell (1), absent Android device (4), opt-in live SDK-role tests (2),
  unavailable DataEngine fixture (1). Eight configured deselections are retained.
  Linux execution is delegated to the new commit's CI; baseline CI alone is not
  evidence for these changes.

## Separate observed defect: history fixture thread race

The second full run, concurrent with isolated wheel installation, encountered
`RuntimeError: cannot join thread before it is started` in
`tests/unit/tools/history/test_search.py::_flush`. Three errors occurred in
fixture setup and one failure at the same `_flush` call inside
`test_excerpts_never_show_raw_json`; there was no failed search-content assertion.
The existing storage runner in `artemis/data_engine/engine.py` appends a thread
to `_pending_threads` before starting it. A snapshot-and-join fixture can observe
that interval, including when storage work schedules more background work.
This is a potential pre-existing synchronization defect, outside plan A's
transport/setup boundary. Neither engine nor fixture was changed to hide it.
The isolated history-search rerun passed **23 tests**; the final full rerun
without concurrent dependency installation passed **2367 tests**. The failed
run remains recorded above, and a pass does not establish that the race is fixed.

## Live acceptance boundary

Read-only normal-host checks with both system Python and the installation `.venv`
found **Codex + Antigravity**. Doctor now reports **READY**, with only Codex in
`ready_providers` and the Antigravity unsupported warning. No AI CLI was launched.
The `.venv` Setup check (`--skip-login-check`) correctly reports
**ACTION_REQUIRED**: Codex's existing Skill is not current for this installation,
no Android device is connected, and Helper readiness is incomplete. Antigravity's
managed Skill is current but its inference remains unsupported. No repair or
provisioning was attempted; existing Skills and user settings remain untouched.
Both Python environments pass `pip check`. These are installation diagnostics,
not live model acceptance or Android success.

| CLI | Setup/Doctor contract | Pro inference | Live model + Android in this review |
| --- | --- | --- | --- |
| Codex | Offline regressions pass | Existing adapter retained | Not run |
| Claude Code | Offline regressions pass | Existing adapter retained | Not run |
| Gemini CLI | Offline regressions pass | Existing adapter retained | Not run |
| Antigravity | Host lifecycle retained; mixed-host warning | UNSUPPORTED | Not run; gate unmet |

No login/settings/Skill files or Android data were changed for acceptance.
Official CLI versions, authentication, image perception, schema output,
retry/cancellation and real Android verdict/Trace consistency remain execution-PC
acceptance tasks. Isolated remover fixtures are not real uninstall evidence.
