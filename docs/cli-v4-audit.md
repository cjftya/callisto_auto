# Callisto v4 CLI boundary audit

Date: 2026-10-19. Start: master `c56d3c7fef578d9e8e2339a410b43ee82cad05d2`,
main `3aa3ccb9a2bc6c8d0e7f70cbd83a59be4e8d5a78` (ancestor of master).
The 32 SHA-256 entries in `upstream-preserved-manifest.json` match at baseline.
No real provider CLI, authentication probe, or Android inference is permitted in Work.

| Files / surface | Decision and evidence | Impact / verification |
| --- | --- | --- |
| `artemis/llm/router.py`, `services/llm.py`, `callisto/llm_adapter/` | Keep CLI factory; reject all legacy API providers before construction. Native-shaped port imports Google data types only. | Provider-denial and native capability tests; static SDK/HTTP boundary audit. |
| `agents/explorer/explorer.py`, `agents/video_analyzer/video_analyzer.py` | Replace key-dependent engine selection with Universal default. Explicit injected native ports remain compatible; never construct SDK clients or read keys. | Existing Universal frame/explorer tests plus key-present/key-absent regressions. Native algorithm tests use explicit fake clients. |
| `config/settings.py`, `third_party/mobile_use/config/llm.py` | Disable unused credential management and ADC validation; retain inert legacy attributes/method signatures where old tests/imports depend on them. | Environment secrets cannot change settings or engine selection; writes/ADC fail explicitly. |
| `utils/ocr_api.py` | Remove unused HTTP client factory and Vision response parser (no callers). Keep opt-in CLI text/polygon contract and optional client argument. | OCR disabled/enabled/error tests; no HTTP transport created. |
| `config/artemis.jsonc`, bundled config, chunker defaults | Replace stale dedicated Gemini model labels with current CLI default `gpt-6.1-sol`; preserve explicit CALLISTO_MODEL override. | Default/config parity; chunker regression. |
| `resources/showcase_ui/`, `resources/__init__.py` | Remove seven browser artifacts and unreferenced browser accessor. | Wheel archive denies web resources and removed runners. |
| `pyproject.toml` | Keep google-genai for `types`, mcp for in-process action contracts, httpx for existing perception signatures, Android/image/notebook dependencies. Remove packages without active imports. Pin mcp below 2: isolated install found FastMCP removed in v2. | Editable and isolated wheel installation, Pro import, pip check, full regression. |
| `mcp/action_session.py`, `mcp/action_server.py`, shared Flash summarizer/compressor, Explorer tiers | Preserve. Internal memory streams/action schemas are used by Pro; these are not an external server or Flash runner. Block leftover adb_server/xml_search_server module launchers with explicit exit errors. | Existing action, cancellation, graph and manifest suites. |
| `config/constants.py`, `config/paths.py`, diagnostics identifiers | Retain inert historical aliases needed by imports/stored reports. They expose no server command. | CLI help and entrypoint tests. No removed daemon implementation exists. |
| `tests/upstream_removed/` | Keep historical excluded tests for removed upstream surfaces. Restore applicable version/config resource contracts to active Callisto suite. | Default discovery excludes historical tree; git preserves source provenance. |
| `skills/callisto/SKILL.md`, `.agents/skills/callisto/SKILL.md` | Keep canonical source; validate the existing discovery pointer (three parents reach repository root). Ship canonical instructions in wheel too. | Pointer resolution, packaged skill availability; Skill delegates to Pro. |
| `.github/workflows/offline.yml` | Validate master/main/PR, Linux full regression, Windows subprocess/CLI contracts, clean wheel installation on both. Add LF attributes for byte-exact preservation checks and install setuptools for non-isolated builds. | Actions evidence must be inspected before main integration. |
| Native Files/Interactions/cache/audio/search | Explicit unsupported errors; retain unused source for provenance, no fake cloud values. | Native port unsupported tests; no live equivalence claim. |

## Official provider interface review

Reviewed 2026-10-19: https://learn.chatgpt.com/docs/cli/reference,
https://learn.chatgpt.com/docs/non-interactive-mode and
https://learn.chatgpt.com/docs/config-file/config-basic .
Codex exec documents stdin (`-`), repeated images, JSONL completion events,
output schema, ephemeral mode, ignore-user-config (authentication still CLI-owned),
read-only sandbox and model/config overrides. Disable provider shell, apps,
plugins, hooks, subagents and web search; ARTEMIS alone executes Android actions.
Official documentation inspection is not a live CLI compatibility result.
Claude text remains experimental; Gemini transport remains unsupported.

## Packaging limitation to report

The source contains Helper build inputs and a version manifest but no APK.
A wheel must not claim bundled auto-install support without the actual binary.
Keep Helper attachment and explicit APK installation; report missing APK clearly.
