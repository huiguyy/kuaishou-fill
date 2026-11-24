"""Local, single-file duplicate guard (not the commercial three-key system)."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import FillError


class FillHistory:
    def __init__(self, path: Path, platform: str) -> None:
        self._path = path
        self._platform = platform

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"version": 1, "entries": {}}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data.get("version") != 1 or not isinstance(data.get("entries"), dict):
                raise ValueError("unsupported history schema")
            return data
        except (OSError, ValueError, TypeError) as exc:
            raise FillError(
                "history_invalid",
                f"Duplicate-history file is unreadable or invalid: {self._path}. "
                "Move it aside before retrying; no upload was attempted.",
                exit_code=2,
            ) from exc

    def _key(self, video_sha256: str) -> str:
        return f"{self._platform}:{video_sha256}"

    def find(self, video_sha256: str) -> dict[str, Any] | None:
        entry = self._read()["entries"].get(self._key(video_sha256))
        if not isinstance(entry, dict):
            return None
        if entry.get("platform") != self._platform or not entry.get("filled"):
            return None
        return entry

    def mark(self, video_sha256: str, fields: list[str], screenshot: Path) -> None:
        data = self._read()
        data["entries"][self._key(video_sha256)] = {
            "platform": self._platform,
            "filled": True,
            "filled_at": datetime.now(timezone.utc).isoformat(),
            "fields": fields,
            "screenshot": str(screenshot),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temp_name = tempfile.mkstemp(prefix=".fill-history-", dir=self._path.parent)
            try:
                os.chmod(temp_name, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, self._path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        except OSError as exc:
            raise FillError(
                "history_write_failed",
                f"Form was filled, but the local duplicate marker could not be saved: {self._path}. "
                "Do not rerun until the history path is writable; the browser remains open for human review.",
                exit_code=5,
            ) from exc
