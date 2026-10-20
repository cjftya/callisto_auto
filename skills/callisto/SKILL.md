---
name: callisto
description: Run natural-language Android tests through Callisto's preserved ARTEMIS Pro graph using an authenticated local AI CLI, ADB and Accessibility Helper.
---

# Callisto

Use the installed Callisto CLI to carry out Android test goals. Callisto, not this
Skill, owns planning, exploration, operation, checking, recovery and reporting.

## Execution environment

- On the user's selected execution machine: use the installed
  provider CLI's own official login. Never read/copy login tokens or convert
  subscription credentials into API calls.
- Run authorized Android tests through `callisto run` and the preserved Pro engine.
  Do not replace test navigation or verification with direct ADB commands.
- For offline development/tests, set `CALLISTO_FORBID_LIVE_CLI=1`; this explicit
  switch blocks real inference independently of the hosting application.
- Callisto creates separate authenticated child processes for inference. It does
  not reuse the hosting assistant's conversation or automatically inherit an
  interactive-only choice. The child CLI reads its own official user defaults.
- Identify the current hosting CLI from the host application (Codex: codex,
  Claude Code: claude, Gemini CLI: gemini, Antigravity CLI: antigravity) and pass it as `--ai-cli` on
  both setup checks and runs. Never guess from installed executables when the
  host is known. Never select a model or a reasoning setting in Callisto.

## Workflow on the local machine

1. Resolve the installed command. If `callisto` is not on PATH, read the adjacent
   `callisto-install.json` (not a login file) and use its `python_executable` as
   `<python> -m callisto.cli` for all commands. This supports the setup venv without
   activation or system PATH changes. Never guess a different project's Python.
2. Run `callisto setup check --json --ai-cli <host-cli>`. It checks configuration, official CLI login
   status, authorized devices, Skill and Helper without model inference. Treat
   ACTION_REQUIRED/UNSUPPORTED as a real stop with the reported next action.
   In offline development use `--skip-login-check`; this is not live readiness.
3. If needed, ask the user to install/login to the provider CLI using its official
   mechanism. Use `adb devices` to identify the device. If multiple devices are
   available, select an explicit serial; do not guess which device to control.
4. A live model acceptance probe is optional and can consume subscription quota.
   Only when explicitly requested, run `python tools/verify_local_cli.py --allow-live-cli`
   from the checkout. Normal setup does not require this probe.
5. Run `callisto run "<goal>" --ai-cli <host-cli> --device-serial <serial> --verification-level final`.
   Use `--expected-output` for an explicit output requirement. Only Pro is available.
6. Collect the printed result-file path and the original ARTEMIS trace artifacts.
   Inspect `run_outcome.json` and `test_summary` before claiming a test passed.
   Exit 1 means failure; exit 2 means incomplete checks; 130 means cancelled.
7. Report unsupported capability, timeout, login, disconnected device and task
   failure clearly. Do not hide failures with fabricated success or reduced tests.

`callisto trace list` and `callisto trace view <session_name>` inspect local
artifacts. No web UI, HTTP daemon or external MCP server is involved.

## Complete uninstall requests

For an explicit request to completely remove Callisto, use the official source
installation's `uninstall.ps1` (Windows) or `uninstall.sh` (Linux). Locate it from
the adjacent registration's `python_executable` under `.venv`; treat metadata as
a hint and verify the root's setup scripts, package metadata and source markers.
Never construct broad recursive deletion commands from registration data.

Run `-DryRun` / `--dry-run` first. Show the exact root, deleted/preserved Skills
and settings, and warn that the ENTIRE root, .venv, internal Traces and extra
personal files are permanently removed. Ask for explicit final approval of this
concrete scope. Only then invoke the same official script with
`-ConfirmRoot '<exact preview root>'` / `--confirm-root '<exact preview root>'`.
Use an external system Python/PowerShell; never run the remover with the target
venv Python. On Windows launch a short-lived PowerShell process with `-File` so
it exits and releases the installation; the worker waits up to 60 seconds.

Default settings are shared and preserved. Only if the user confirms no other
installation uses them, include `-RemoveSettings` / `--remove-settings` in BOTH
preview and approved invocation. Custom `CALLISTO_CONFIG` paths and unrecognized
content are preserved. Do not infer absence of other installs from registrations.
`SCHEDULED` is not success: read the external `result.json` and report removed,
failed and preserved paths. Do not terminate the hosting AI CLI to unlock files.
If scripts/metadata are missing or damaged, give README's manual removal guide
and verify paths with the user; do not bypass checks or touch AI CLI credentials,
system Python/ADB, device Helper, external files or other installations.

## Capability boundaries

Antigravity CLI (`agy`) host registration uses
`~/.gemini/antigravity-cli/skills/callisto/`; the IDE/app directory is separate
and is not installed. Pass `--ai-cli antigravity` for this host. Pro inference
is currently UNSUPPORTED: non-tool image input and complete CLI tool blocking
have not been validated. Stop at setup's UNSUPPORTED result; never fall back to
Gemini or another provider, omit screenshots or ask agy to read them with tools.
Skill registration and filesystem status do not prove host recognition or E2E.

The Codex, Claude and Gemini adapters support image-bearing requests and
structured agent responses in offline contract tests. The installed official
CLI version, login and actual Android vision accuracy must be tested locally.
Gemini is launched in read-only plan mode; its internal image-loading and
tool event boundaries still require local validation. Google-native Files, Interactions, explicit cloud
caches, audio and server-side search have no validated CLI equivalent and must
not be reported as supported. See `docs/cli-capability-matrix.md`.

## Image policy and usage

Default balanced resizes only transmitted images (1920px long edge, JPEG 80).
Use `--image-policy quality` or `off` for unreadable small text, without disabling
verification. Existing Explorer region inspection/crop decisions remain in Pro;
do not introduce independent navigation or retry loops in this Skill.
The result and usage JSON paths report measured CLI tokens, image counts and time.
Unknown usage is not zero. Cached input is part of total input, not additional input.
Report successful verification only from the original verdict (0/1/2/130).
