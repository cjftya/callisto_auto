# Antigravity CLI integration evidence

Date: 2026-10-21. Scope: host discovery, Skill lifecycle and explicit unsupported
inference boundary. The preserved Pro engine and preservation manifests are unchanged.

## Official interface and local evidence

- [Official skills documentation](https://www.antigravity.google/docs/skills/)
  identifies `~/.gemini/antigravity-cli/skills/` as the CLI global directory.
  IDE/app `~/.gemini/config/skills/` is separate and excluded.
- [Official quickstart](https://www.antigravity.google/docs/getting-started)
  identifies Windows `%LOCALAPPDATA%/agy/bin` and Linux `~/.local/bin/agy`.
- [Official headless documentation](https://www.antigravity.google/docs/cli/headless/)
  documents JSON/schema output and stream input with text blocks only.
  JSON success is `SUCCESS`; stream tool events describe actual execution.
  These documented response/usage shapes have not been validated as a Callisto transport.
- [Official permissions documentation](https://www.antigravity.google/docs/permissions/)
  describes global permission rules. A complete isolated per-request tool-disable
  contract has not been verified; plan/sandbox alone does not establish it.
- On this Windows PC the official binary is
  `C:\Users\cjfty\AppData\Local\agy\bin\agy.exe`. `--version` returned **1.4.2**.
  `--help` lists print, JSON, schema, stream input, mode and sandbox options, but
  no image attachment or complete tool-disable option. No unsafe permission flag was used.
  Initial sandbox PATH lookup could not see the installation; a normal host check
  confirmed it. This was an access limitation, not evidence of absence.
- Actual global Skill registration passed: managed/current, package 0.1.2,
  exactly `SKILL.md` and `callisto-install.json`, pointing to this checkout's
  `.venv\Scripts\python.exe`. Filesystem registration does not prove TUI recognition.
- `setup check --json --skip-login-check --ai-cli antigravity` detects the native
  binary and current Skill, reports **UNSUPPORTED**, and found no Android device.
  Login/keyring was not inspected. No inference was launched.

## Implemented boundary

`antigravity` selects `agy`, including PATH, explicit non-secret executable setting
and official installation fallback. Shell wrappers and non-native binaries are rejected.
Setup/repair and Skill install/update/status register the canonical two-file bundle.
PowerShell setup validates the new host; shell setup forwards to the shared bootstrap.
The existing remover includes this CLI's managed Skill, with unchanged modified,
unmanaged, foreign-install and extra-file preservation checks. No real uninstall ran.

Run, model transport, stdin encoding and result decoding reject Antigravity inference
before launching a child, consuming an image or starting Android. There is no fallback,
image omission, file-reading tool workaround or direct API call. No unvalidated JSON
decoder or fabricated usage mapping is exposed. Official CLI model defaults remain untouched.

## Outstanding acceptance

Pro support requires a verified official non-tool multimodal image route, complete
tool blocking, live schema/content/tool-call data and usage validation, timeout/cancel
acceptance and Android Pro trace/verdict E2E. Authentication, `/callisto` recognition,
headless text/image inference, Linux live execution and Android E2E remain unverified.
The current adapter deliberately cannot run a text-only substitute for Pro acceptance.

## Offline validation

Normal Windows host, Python 3.13.15, `CALLISTO_FORBID_LIVE_CLI=1`:

- `python -m pytest -q`: **2336 passed, 10 skipped, 8 deselected**.
  Includes Codex/Claude/Gemini contracts, preservation hashes, Antigravity tests
  and managed removal/modified preservation across all four host directories.
- The 12 Antigravity tests also passed independently. Windows/Linux path tests
  are offline simulations; actual Linux execution remains unverified.
- `python -m pip check`: passed for system test Python and project `.venv`.
- Ruff on changed Python files and `git diff --check`: passed.
- Frontend-free `python -m pip wheel --no-deps --no-build-isolation -w dist .`:
  passed. Changed runtime modules match the final wheel byte for byte.
- Source/wheel Helper APK SHA-256 matches
  `73590b206d576abd24beb0d35aee2657b6bd65af1e060db188e0a5de3365d6ec`.
  Final clean-venv `tools/verify_wheel.py --require-helper` verification passed,
  including isolated installation, `pip check`, Pro imports, CLI help, canonical
  Skill lifecycle and Helper manifest/APK validation. No model CLI was executed.

During validation, the existing remover once refused an external test worker
because related processes were present. The final complete suite passed without
weakening process checks. Expanding the removal fixture initially exposed a missing
test-only parent directory, corrected before the final suite. No live parity claim
is made from these offline results.
