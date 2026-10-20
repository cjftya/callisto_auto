#!/usr/bin/env sh
set -eu
# Resolve the script location, never the caller's working directory.
CALLISTO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -L)
for CALLISTO_PYTHON in python3.12 python3 python; do
    if command -v "$CALLISTO_PYTHON" >/dev/null 2>&1 && "$CALLISTO_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'; then
        exec "$CALLISTO_PYTHON" "$CALLISTO_ROOT/tools/uninstall.py" "$@"
    fi
done
printf '%s\n' 'ACTION_REQUIRED: Python 3.12+ is required. See README for manual removal.' >&2
exit 1
