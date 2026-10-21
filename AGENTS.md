# Callisto working rules

- Run authorized live model/Android acceptance through the installed official AI
  CLI and the preserved Pro engine on the selected execution machine.
  `callisto doctor` checks paths/config without executing provider CLIs.
  Set `CALLISTO_FORBID_LIVE_CLI=1` for offline tests and fake Python child processes.
  A nested CLI launch failure alone is not evidence of unsupported transport.
- Preserve upstream Pro graph, prompts, agent decisions, state, checkpoints,
  recovery, ADB/Helper and local in-process action sessions. Keep model changes
  at transport/configuration boundaries. Do not replace agents with Skill logic.
- Do not add direct LLM API calls or extract/copy credentials. CLI login is owned
  by the official installed CLI. Keep unsupported media/native features explicit.
- Web UI, HTTP daemon, external MCP entrypoints and the Flash execution runner
  are excluded. Shared summarizer/compressor modules and Explorer's `flash` tier
  are still used by Pro and must remain.
- Run `python -m pytest`, `python -m pip check`, and a frontend-free wheel build
  after relevant implementation changes. Report skipped host/device checks.
  Tests requiring a matching real PID/procfs view run on normal hosts/CI, not
  against a mismatched Work PID namespace.
- Keep original licenses and source SHA. Update the architecture and capability matrix
  with current evidence; never equate mock success with live parity.

- Preserve LF checkouts (`.gitattributes`) so the upstream manifest also checks
  exact bytes on Windows. Do not regenerate the preservation hashes to hide drift.
- Keep `mcp<2`: Pro uses the v1 FastMCP in-process API. Upgrade only with explicit
  action-session equivalence tests. Google SDK is retained for data types only.
- Build without frontend: install `setuptools wheel`, run `pip wheel --no-deps
  --no-build-isolation -w dist .`, then `python tools/verify_wheel.py <wheel>`.
  The latter creates a clean venv; help/import checks never execute AI CLIs.
- The canonical Skill is `skills/callisto/SKILL.md`; the discovery pointer and
  wheel package must use that source. The canonical source bundle includes the
  CI-built Helper APK and matching manifest. Preserve Helper source and the
  historical `helper/` artifact. Validate the APK/manifest pair and APK-bearing
  wheel before claiming bundled provisioning passed; device installation remains
  a separate acceptance check.

## Current documentation and cleanup boundary

- Read `docs/architecture.md` for the current structure, `docs/cli-capability-matrix.md`
  for support limits, and `docs/advanced-setup.md` for current operation. README
  owns user setup; the canonical Skill owns host routing and execution steps.
- The remote SDK DESIGN/example and `tests/upstream_removed/`
  are historical evidence, not current execution or model configuration guidance.
  Do not restore obsolete model pins, daemon commands or branch instructions.
- Cleanup must preserve observable behavior, defaults, public imports/paths,
  launch contracts, image/coordinate policy, Helper and verdicts. Record potential
  functional defects separately. Unknown usage is a reason to retain a file.
- Keep both `artemis_client/` trees: direct checkout imports use the root copy;
  wheel and standalone SDK builds use `packages/artemis-client/src/`. They are
  public compatibility code, not proof that Callisto serves a remote daemon.
- Do not remove apparently unused re-exports, import aliases or prompt resources
  merely from lint results. Preservation manifests are immutable evidence.
- Record cleanup evidence in Git commits; do not append old release
  histories to active architecture/support guides.
