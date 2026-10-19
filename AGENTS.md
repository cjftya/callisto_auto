# Callisto working rules

- In ChatGPT Work, never execute a real AI CLI (`codex`, `claude`, `gemini`),
  including login/status/version probes. Never run `callisto run` or
  `tools/verify_local_cli.py --allow-live-cli` there. Use offline tests and fake
  Python child processes only. `callisto doctor` checks paths/config without
  executing provider CLIs. Set `CALLISTO_FORBID_LIVE_CLI=1` for offline work.
- Live model/Android acceptance belongs on the user's actual execution machine.
  A failed nested CLI launch in Work is not evidence that the local CLI adapter
  is unsupported and is not a reason to stop implementation.
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
- Keep original licenses and source SHA. Update the capability matrix and
  migration status with evidence; never equate mock success with live parity.
