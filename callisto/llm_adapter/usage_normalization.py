"""Provider usage contracts. Missing counters are unknown, never inferred zero.

Scope describes the returned counter, not a persistent CLI session. No cumulative
counter is added to run totals or passed to the transcript context-pressure gate.
"""
from copy import deepcopy

VERSION = "callisto-usage-v1"
COUNTERS = ("logical_input_tokens", "uncached_input_tokens", "cache_read_tokens",
            "cache_write_tokens", "output_tokens", "thought_tokens")


def counter(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def normalize_usage(provider, raw, *, scope="unknown", context_is_single_request=False):
    raw = raw if isinstance(raw, dict) else {}
    result = {key: None for key in COUNTERS}
    result.update(raw_usage=deepcopy(raw), usage_scope=scope if scope in
                  ("request", "invocation", "session_cumulative") else "unknown",
                  usage_semantics_version=VERSION, context_input_tokens=None)
    def get(name):
        return counter(raw.get(name))
    if provider == "codex":
        result.update(logical_input_tokens=get("input_tokens"),
                      cache_read_tokens=get("cached_input_tokens"), output_tokens=get("output_tokens"))
    elif provider == "claude":
        fresh, read, write = (get(k) for k in
                            ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        result.update(uncached_input_tokens=fresh, cache_read_tokens=read,
                      cache_write_tokens=write, output_tokens=get("output_tokens"))
        if all(v is not None for v in (fresh, read, write)):
            result["logical_input_tokens"] = fresh + read + write
    elif provider == "gemini":
        # Versioned models.*.tokens contract only. Unknown shapes stay unknown.
        models = raw.get("models")
        if isinstance(models, dict) and models:
            rows = [m.get("tokens", {}) if isinstance(m, dict) else {} for m in models.values()]
            for target, aliases in (("logical_input_tokens", ("prompt", "promptTokens")),
                                    ("output_tokens", ("response", "candidates", "outputTokens")),
                                    ("cache_read_tokens", ("cached",)), ("thought_tokens", ("thoughts",))):
                values = [next((counter(row[k]) for k in aliases if counter(row.get(k)) is not None), None)
                          if isinstance(row, dict) else None for row in rows]
                if all(v is not None for v in values):
                    result[target] = sum(values)
    total, read = result["logical_input_tokens"], result["cache_read_tokens"]
    if provider in ("codex", "gemini") and total is not None and read is not None and read <= total:
        result["uncached_input_tokens"] = total - read
    if read is not None and total is not None and read > total:
        result["logical_input_tokens"] = None  # inconsistent fixture, fail closed
    if result["usage_scope"] == "request" or (result["usage_scope"] == "invocation" and context_is_single_request):
        result["context_input_tokens"] = result["logical_input_tokens"]
    return result
