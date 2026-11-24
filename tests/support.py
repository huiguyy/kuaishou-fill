from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_PARENT = ROOT / "src" if (ROOT / "src" / "fillup_core").is_dir() else ROOT / "scripts"
if str(CORE_PARENT) not in sys.path:
    sys.path.insert(0, str(CORE_PARENT))


def platforms() -> tuple[str, ...]:
    if (ROOT / "skills").is_dir():
        return ("douyin", "kuaishou")
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    return ("kuaishou",) if "name: kuaishou-fill" in text else ("douyin",)


def script_dir(platform: str) -> Path:
    return ROOT / "skills" / f"{platform}-fill" / "scripts" if (ROOT / "skills").is_dir() else ROOT / "scripts"


def cli_path(platform: str) -> Path:
    return script_dir(platform) / f"{platform}_fill.py"


def atom(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def faststart_bytes() -> bytes:
    return atom(b"ftyp", b"isom0000") + atom(b"moov") + atom(b"mdat", b"video")
