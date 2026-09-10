#!/bin/sh
# macOS/Linux launcher; installation and offline checks are shared with Windows.
set -eu
REPO_DIR=$(CDPATH= cd -P -- "$(dirname -- "$0")" && pwd)
cd "$REPO_DIR"
VENV_PYTHON="$REPO_DIR/.venv/bin/python"

compatible_python() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1
}

if [ ! -x "$VENV_PYTHON" ] || ! compatible_python "$VENV_PYTHON"; then
    PYTHON_CMD=
    if [ -n "${PSYVIEW_PYTHON:-}" ]; then
        if compatible_python "$PSYVIEW_PYTHON"; then
            PYTHON_CMD=$PSYVIEW_PYTHON
        else
            echo "ERROR: PSYVIEW_PYTHON must name a working Python 3.12+ executable." >&2
            exit 1
        fi
    else
        for candidate in python3.13 python3.12 python3 python; do
            if command -v "$candidate" >/dev/null 2>&1 && compatible_python "$candidate"; then
                PYTHON_CMD=$candidate
                break
            fi
        done
    fi
    if [ -z "$PYTHON_CMD" ]; then
        echo "ERROR: PsyView requires Python 3.12+. Install Python 3.13 from python.org, reopen Terminal, and try again." >&2
        echo "You can also set PSYVIEW_PYTHON to the full path of a compatible Python executable." >&2
        exit 1
    fi
    "$PYTHON_CMD" scripts/launcher_setup.py --create
fi

"$VENV_PYTHON" scripts/launcher_setup.py
echo "[PsyView] Starting PsyView"
exec "$VENV_PYTHON" -m psyview "$@"
