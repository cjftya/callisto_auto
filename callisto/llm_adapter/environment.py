"""Child-only authentication policy; saved login stays owned by the official CLI.

Never inspect credential files or mutate the parent environment. API-key and
alternate-provider overrides are omitted, including mixed-case Windows keys.
HOME/USERPROFILE, CODEX_HOME and CLAUDE_CONFIG_DIR keep their normal meaning.
"""

import os

API_KEY_VARIABLES = frozenset({
    "OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_AWS_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_API_KEY",
    "AZURE_OPENAI_API_KEY", "AZURE_API_KEY", "OCR_API_KEY",
})

PROVIDER_OVERRIDES = {
    "codex": frozenset({"OPENAI_BASE_URL", "OPENAI_API_BASE", "AZURE_OPENAI_ENDPOINT"}),
    "gemini": frozenset({"GOOGLE_GEMINI_BASE_URL"}),
    "claude": frozenset({
        "ANTHROPIC_BASE_URL", "ANTHROPIC_AWS_BASE_URL", "ANTHROPIC_AWS_WORKSPACE_ID",
        "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
        "AWS_BEARER_TOKEN_BEDROCK", "ANTHROPIC_FOUNDRY_API_KEY",
        "ANTHROPIC_FOUNDRY_BASE_URL", "ANTHROPIC_VERTEX_PROJECT_ID",
    }),
}


def cli_environment(provider: str | None = None, *, source=None) -> dict[str, str]:
    if provider is not None and provider not in PROVIDER_OVERRIDES:
        raise ValueError("Unknown CLI environment policy")
    blocked = API_KEY_VARIABLES | PROVIDER_OVERRIDES.get(provider, frozenset())
    source = os.environ if source is None else source
    # Select by name before accessing values. Official CLI OAuth login and
    # standard OS/keychain discovery are inherited normally, never extracted.
    return {key: source[key] for key in source if key.upper() not in blocked and key.upper() != "CLAUDECODE"}
