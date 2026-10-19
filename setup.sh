#!/usr/bin/env sh
set -eu
CALLISTO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for CALLISTO_PYTHON in python3.12 python3 python; do
    if command -v "$CALLISTO_PYTHON" >/dev/null 2>&1 && "$CALLISTO_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)'; then
        exec "$CALLISTO_PYTHON" "$CALLISTO_ROOT/tools/bootstrap.py" "$@"
    fi
done
printf '%s\n' 'ACTION_REQUIRED: Install Python 3.12+ with pip/venv, then rerun ./setup.sh.' >&2
exit 1
