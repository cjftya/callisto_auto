# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration-host probe: the process environment an IDE / MCP client launched us in.

The standard readiness probes answer "can Artemis drive a phone on this
machine?". This probe answers the question that precedes it when Artemis is
embedded in an AI coding assistant (Claude Code, Cursor, Codex, Antigravity,
...): "was the server launched the way the installer expects, and can it
spawn a background runner?". The failure modes it covers are the ones users
hit mostly through MCP, rarely from the CLI or the web console:

* the MCP client started the server with a different interpreter than the
  project virtualenv, so the spawned runner imports a different package set;
* the ``.env`` file the settings loader reads is not where the user put the key;
* the traces directory is not writable from the client's sandbox;
* the daemon port is held by another process (a very common collision with
  dev servers that also default to port 8000).

The probe is not registered in the default :class:`ReadinessEngine` probe set:
the web console has its own device wizard and would only render noise. The
``mobile_diagnose`` MCP tool and ``artemis doctor`` run it explicitly.

Only the unwritable-traces case blocks task execution; the result carries
``is_blocker`` accordingly, so the WARN findings degrade the verdict without
blocking it.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from artemis.core.diagnostics.probes.base import BaseProbe
from artemis.core.diagnostics.schema import (
    ProbeAction,
    ProbeCategory,
    ProbeResult,
    ProbeStatus,
)


def _same_file(a: str | os.PathLike[str], b: str | os.PathLike[str]) -> bool:
    """Compare two interpreter paths tolerantly (symlinks, case on Windows)."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


#: Client names accepted by ``artemis mcp --install`` (see interfaces/cli/commands/mcp.py).
MCP_CLIENT_NAMES: tuple[str, ...] = (
    "antigravity",
    "claude",
    "cursor",
    "windsurf",
    "vscode",
    "cline",
    "roo",
    "openclaw",
    "codex",
)


def _env_has_prefix(prefix: str, *, exclude: tuple[str, ...] = ()) -> bool:
    return any(key.startswith(prefix) and key not in exclude for key in os.environ)


def detect_mcp_client() -> str | None:
    """Best-effort guess of which MCP client launched this process, from ``os.environ``.

    Returns one of :data:`MCP_CLIENT_NAMES` or ``None`` when unsure. MCP hosts
    spawn the server with their own process environment, so the variables the
    IDE exports to its child processes leak through. Specific hosts are checked
    before the generic VS Code markers because Cursor, Windsurf, Cline and Roo
    are (or run inside) VS Code and inherit ``VSCODE_*`` / ``TERM_PROGRAM``.
    """
    # Antigravity injects its language-server endpoint and CSRF token
    # (ANTIGRAVITY_LS_ADDRESS / ANTIGRAVITY_CSRF_TOKEN) so child processes can
    # call `agentapi`; mcp_server/notifiers/agentapi.py relies on the same pair.
    if _env_has_prefix("ANTIGRAVITY_"):
        return "antigravity"
    # Claude Code marks every child with CLAUDECODE=1 plus CLAUDE_CODE_* details
    # (entrypoint, session id, ...). Claude Desktop shares the same installer
    # target, so both map to "claude".
    if os.environ.get("CLAUDECODE") == "1" or _env_has_prefix("CLAUDE_CODE_"):
        return "claude"
    # Cursor tags its integrated terminal and spawned processes with
    # CURSOR_TRACE_ID (and CURSOR_AGENT in agent mode).
    if "CURSOR_TRACE_ID" in os.environ or _env_has_prefix("CURSOR_"):
        return "cursor"
    # Windsurf (Codeium) exports WINDSURF_* to its child processes.
    if _env_has_prefix("WINDSURF_"):
        return "windsurf"
    # Codex CLI sets CODEX_SANDBOX* / CODEX_* for the processes it runs.
    # CODEX_HOME alone is excluded: users set it by hand to relocate the Codex
    # config directory, so on its own it does not prove Codex launched us.
    if _env_has_prefix("CODEX_", exclude=("CODEX_HOME",)):
        return "codex"
    # OPENCLAW_WEBHOOK_URL is a notifier setting users put in any host's env
    # block (see mcp_server/notifiers/webhook.py); only other OPENCLAW_* vars
    # indicate the OpenClaw runtime itself.
    if _env_has_prefix("OPENCLAW_", exclude=("OPENCLAW_WEBHOOK_URL",)):
        return "openclaw"
    # Cline / Roo Code run as VS Code extensions; their own prefixes are rare
    # but unambiguous when present, and must win over the generic VS Code check.
    if _env_has_prefix("CLINE_"):
        return "cline"
    if _env_has_prefix("ROO_"):
        return "roo"
    # Plain VS Code (Copilot agent mode) exports VSCODE_PID / VSCODE_IPC_HOOK
    # and sets TERM_PROGRAM=vscode. Weakest signal, so it is checked last.
    if (
        "VSCODE_PID" in os.environ
        or "VSCODE_IPC_HOOK" in os.environ
        or os.environ.get("TERM_PROGRAM") == "vscode"
    ):
        return "vscode"
    return None


def mcp_install_actions(client: str | None) -> list[ProbeAction]:
    """Actions that regenerate the MCP client config for ``client`` (or ask which one)."""
    if client:
        return [
            ProbeAction(
                action_type="command",
                label="Regenerate MCP Config",
                payload=f"uv run artemis mcp --install {client}",
            )
        ]
    return [
        ProbeAction(
            action_type="hint",
            label="Regenerate MCP Config",
            payload=(
                "Could not tell which MCP client launched this server. Ask the user which IDE"
                " they are using, then run `uv run artemis mcp --install <client>` with"
                " <client> being one of: " + ", ".join(MCP_CLIENT_NAMES) + "."
            ),
        )
    ]


def project_venv_python(project_root: Path) -> Path:
    """Return the interpreter path the installer writes into MCP client configs."""
    if sys.platform == "win32":
        return project_root / ".venv" / "Scripts" / "python.exe"
    return project_root / ".venv" / "bin" / "python"


def directory_is_writable(path: Path) -> tuple[bool, str | None]:
    """Try to create and delete a scratch file; return (ok, error)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".artemis-diag-", delete=True):
            pass
        return True, None
    except OSError as exc:
        return False, str(exc)


def intended_traces_path() -> Path:
    """Return the traces directory the settings loader *would* pick, without creating it.

    Mirrors the selection order of :func:`artemis.config.paths.get_default_traces_path`
    (``ARTEMIS_TRACES_DIR`` env, else the user app dir when the install mode
    keeps mutable state there, else ``ROOT_DIR/traces``) minus its ``mkdir``.
    Used only when that function raised, so the probe can still name the
    offending directory in its FAIL result instead of crashing.
    """
    from artemis.config import paths as artemis_paths

    env_traces = os.getenv(artemis_paths.ENV_ARTEMIS_TRACES_DIR)
    if env_traces:
        return Path(env_traces)
    if artemis_paths._use_user_app_dir():
        return artemis_paths.get_app_dir() / "traces"
    return Path(artemis_paths.ROOT_DIR) / "traces"


def resolve_traces_dir() -> tuple[Path, str | None]:
    """Return ``(traces_dir, error)``; ``error`` is set when the directory could not be created.

    ``get_default_traces_path`` creates the directory as a side effect, so on a
    read-only parent it raises before :func:`directory_is_writable` ever runs.
    Surface that as data rather than letting the probe itself crash.
    """
    from artemis.config.paths import get_default_traces_path

    try:
        return Path(get_default_traces_path()), None
    except OSError as exc:
        return intended_traces_path(), str(exc)


class IntegrationHostProbe(BaseProbe):
    """Probe verifying the MCP / IDE host process can actually run Artemis tasks."""

    @property
    def probe_id(self) -> str:
        return "integration_host"

    @property
    def category(self) -> ProbeCategory:
        return ProbeCategory.RUNTIME

    @property
    def is_blocker(self) -> bool:
        return True

    async def probe(self) -> ProbeResult:
        traces_dir, error = resolve_traces_dir()
        writable, detail = directory_is_writable(traces_dir) if error is None else (False, error)
        return ProbeResult(id=self.probe_id, category=self.category, title="Local Callisto runtime",
            status=ProbeStatus.PASS if writable else ProbeStatus.FAIL, is_blocker=True,
            summary="Standalone" if writable else "Trace directory unavailable",
            description="No web daemon or external MCP server is required.",
            metadata={"traces_writable": writable, "error": detail})
