---
name: callisto
description: Run natural-language Android tests through Callisto's preserved ARTEMIS Pro graph using an authenticated local AI CLI, ADB and Accessibility Helper.
---

# Callisto

Use the installed Callisto CLI to carry out Android test goals. Callisto, not this
Skill, owns planning, exploration, operation, checking, recovery and reporting.

## Execution environment

- In ChatGPT Work: **do not execute any AI-provider CLI, `callisto run`, or the
  live acceptance script.** Implement/review code and run offline mocked tests
  only. Give the user the local-machine commands below for real inference/device tests.
- On the user's explicitly selected local execution machine: use the installed
  provider CLI's own official login. Never read/copy login tokens or convert
  subscription credentials into API calls.
- Callisto creates separate provider CLI child processes and transmits the full
  agent message history. It does not reuse the hosting assistant's current conversation.

## Workflow on the local machine

1. Run `callisto doctor --json`. This checks installation/configuration; it does
   **not** prove login, model capability, or Android connectivity.
2. If needed, ask the user to install/login to the provider CLI using its official
   mechanism. Use `adb devices` to identify the device. If multiple devices are
   available, select an explicit serial; do not guess which device to control.
3. On first setup, run `python tools/verify_local_cli.py --allow-live-cli` from the
   Callisto checkout. Treat failures and unsupported features as failures.
4. Run `callisto run "<goal>" --device-serial <serial> --verification-level final`.
   Use `--expected-output` for an explicit output requirement. Only Pro is available.
5. Collect the printed result-file path and the original ARTEMIS trace artifacts.
   Inspect `run_outcome.json` and `test_summary` before claiming a test passed.
   Exit 1 means failure; exit 2 means incomplete checks; 130 means cancelled.
6. Report unsupported capability, timeout, login, disconnected device and task
   failure clearly. Do not hide failures with fabricated success or reduced tests.

`callisto trace list` and `callisto trace view <session_name>` inspect local
artifacts. No web UI, HTTP daemon or external MCP server is involved.

## Capability boundaries

Codex is the initial implemented image transport. Claude text transport is
experimental and requires `CALLISTO_AI_CLI=claude` plus `CALLISTO_MODEL`.
Gemini CLI is not implemented. Google-native Files, Interactions, explicit cloud
caches, audio and server-side search have no validated CLI equivalent and must
not be reported as supported. See `docs/cli-capability-matrix.md`.
