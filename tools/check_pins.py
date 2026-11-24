#!/usr/bin/env python3
"""Require exact runtime dependency pins in requirements.txt and pyproject.toml."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PIN = re.compile(r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.!+-]+$")


def check(root: Path) -> list[str]:
    issues: list[str] = []
    requirements = root / "requirements.txt"
    if not requirements.exists():
        issues.append("missing requirements.txt")
    else:
        for number, raw in enumerate(requirements.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if line and not line.startswith("#") and not PIN.fullmatch(line):
                issues.append(f"requirements.txt:{number}: expected exact name==version pin: {line}")
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        in_dependencies = False
        for number, raw in enumerate(pyproject.read_text(encoding="utf-8").splitlines(), 1):
            stripped = raw.strip()
            if stripped == "dependencies = [":
                in_dependencies = True
                continue
            if in_dependencies and stripped == "]":
                in_dependencies = False
                continue
            if in_dependencies and stripped and not stripped.startswith("#"):
                match = re.match(r'["\']([^"\']+)["\']', stripped)
                if not match or not PIN.fullmatch(match.group(1)):
                    issues.append(f"pyproject.toml:{number}: dependency is not exactly pinned")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    issues = check(root)
    if issues:
        print("\n".join(f"FAIL {issue}" for issue in issues), file=sys.stderr)
        return 1
    print("PASS exact runtime dependency pins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
