#!/usr/bin/env python3
"""Static fill-only and dependency-direction gate; intentionally fails on direct clicks."""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

FORBIDDEN_IMPORTS = {"services", "db", "config", "sqlite3", "psycopg", "patchright"}
FORBIDDEN_TEXT = ("--submit", "mark_submitted", "publish_clicked", "_SAU_ROOT", "content-rater")


def _scripts(root: Path) -> list[Path]:
    if (root / "skills").is_dir():
        return sorted((root / "skills").glob("*-fill/scripts/**/*.py"))
    return sorted((root / "scripts").glob("**/*.py"))


def check(root: Path) -> list[str]:
    issues: list[str] = []
    files = _scripts(root)
    if not files:
        return ["no skill scripts found"]
    for path in files:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_TEXT:
            if marker in text:
                issues.append(f"{relative}: forbidden marker {marker!r}")
        try:
            tree = ast.parse(text, filename=relative)
        except SyntaxError as exc:
            issues.append(f"{relative}: syntax error {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                        issues.append(f"{relative}:{node.lineno}: forbidden import {alias.name}")
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                issues.append(f"{relative}:{node.lineno}: forbidden import {node.module}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "click":
                allowed = relative.endswith("scripts/fillup_core/policy.py")
                if not allowed:
                    issues.append(f"{relative}:{node.lineno}: direct .click() bypasses guarded_click")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "press":
                if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value in {"Enter", "NumpadEnter"}:
                    issues.append(f"{relative}:{node.lineno}: Enter can implicitly submit the form and is forbidden")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "evaluate":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and ".click(" in arg.value:
                        issues.append(f"{relative}:{node.lineno}: JavaScript click is forbidden")
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
    print("PASS fill-only click gate and dependency direction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
