# Archived upstream tests

Historical source for web/admin UI, HTTP daemon, external MCP, standalone Flash
and direct provider APIs removed during the CLI migration. These tests describe
removed upstream contracts, not current Callisto capabilities or instructions.

The original files remain for provenance: obsolete web/admin UI, HTTP daemon,
external MCP, standalone Flash and direct-model API contracts. Git retains
file-level deletion history. Default pytest testpaths exclude this directory;
current regression tests live in `tests/callisto`, `tests/unit`, `tests/tools` and
`packages/artemis-client/tests`. Do not move failing active tests here to make CI
pass. Internal in-process MCP and shared Pro/Flash summarizers remain active.

See `docs/architecture.md` and `docs/cli-capability-matrix.md` for current behavior.
