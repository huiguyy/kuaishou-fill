#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CACHE=$(mktemp -d "${TMPDIR:-/tmp}/fillup-checks.XXXXXX")
trap 'find "$CACHE" -delete' EXIT HUP INT TERM
export PYTHONPYCACHEPREFIX="$CACHE"
export PYTHONDONTWRITEBYTECODE=1
python3 -I -B "$ROOT/tools/check_redlines.py" --root "$ROOT"
find "$ROOT/scripts" "$ROOT/src" -type f -name '*.py' -print0 2>/dev/null | xargs -0 -r python3 -B -m py_compile
if [ -d "$ROOT/src/fillup_core" ]; then
  python3 -I -B "$ROOT/tools/vendor_core.py" --check
fi
python3 -I -B "$ROOT/tools/check_fill_only.py" --root "$ROOT"
python3 -I -B "$ROOT/tools/check_pins.py" --root "$ROOT"
if [ -d "$ROOT/skills" ]; then
  for cli in "$ROOT"/skills/*-fill/scripts/*_fill.py; do
    python3 -I -B -S "$cli" --help >/dev/null
  done
else
  python3 -I -B -S "$ROOT"/scripts/*_fill.py --help >/dev/null
fi
python3 -I -B -m unittest discover -s "$ROOT/tests" -v
python3 -I -B "$ROOT/tools/check_redlines.py" --root "$ROOT"
