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
- Callisto creates separate provider CLI child processes and transmits the full
  agent message history. It does not reuse the hosting assistant's current conversation.

## Workflow on the local machine

1. Resolve the installed command. If `callisto` is not on PATH, read the adjacent
   `callisto-install.json` (not a login file) and use its `python_executable` as
   `<python> -m callisto.cli` for all commands. This supports the setup venv without
   activation or system PATH changes. Never guess a different project's Python.
2. Run `callisto setup check --json`. It checks configuration, official CLI login
   status, authorized devices, Skill and Helper without model inference. Treat
   ACTION_REQUIRED/UNSUPPORTED as a real stop with the reported next action.
   In offline development use `--skip-login-check`; this is not live readiness.
3. If needed, ask the user to install/login to the provider CLI using its official
   mechanism. Use `adb devices` to identify the device. If multiple devices are
   available, select an explicit serial; do not guess which device to control.
4. A live model acceptance probe is optional and can consume subscription quota.
   Only when explicitly requested, run `python tools/verify_local_cli.py --allow-live-cli`
   from the checkout. Normal setup does not require this probe.
5. Run `callisto run "<goal>" --device-serial <serial> --verification-level final`.
   Use `--expected-output` for an explicit output requirement. Only Pro is available.
6. Collect the printed result-file path and the original ARTEMIS trace artifacts.
   Inspect `run_outcome.json` and `test_summary` before claiming a test passed.
   Exit 1 means failure; exit 2 means incomplete checks; 130 means cancelled.
7. Report unsupported capability, timeout, login, disconnected device and task
   failure clearly. Do not hide failures with fabricated success or reduced tests.

`callisto trace list` and `callisto trace view <session_name>` inspect local
artifacts. No web UI, HTTP daemon or external MCP server is involved.

## Capability boundaries

Codex is the initial implemented image transport. Claude text transport is
experimental and uses `CALLISTO_AI_CLI=claude` to select the transport.
Gemini CLI is not implemented. Google-native Files, Interactions, explicit cloud
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
