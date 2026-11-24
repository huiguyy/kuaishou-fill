#!/usr/bin/env python3
"""Standalone Kuaishou fill-only CLI; safe --help without Playwright installed."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from kuaishou_adapter import fill_kuaishou
from fillup_core.cli import main


if __name__ == "__main__":
    raise SystemExit(main("kuaishou", Path(__file__).name, fill_kuaishou))
