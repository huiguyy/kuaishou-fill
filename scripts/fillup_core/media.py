"""Offline media validation; never rewrites the user's source files."""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from .errors import FillError

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise FillError("media_unreadable", f"Cannot read media file: {path}", exit_code=2) from exc
    return digest.hexdigest()


def mp4_faststart(path: Path) -> bool:
    """Return whether moov precedes the first top-level mdat atom."""
    try:
        size_on_disk = path.stat().st_size
        with path.open("rb") as handle:
            offset = 0
            moov_offset: int | None = None
            for _ in range(10_000):
                if offset >= size_on_disk:
                    break
                header = handle.read(8)
                if len(header) != 8:
                    raise FillError("invalid_video", "The MP4 contains a truncated atom header.", exit_code=2)
                atom_size, atom_type = struct.unpack(">I4s", header)
                header_size = 8
                if atom_size == 1:
                    extended = handle.read(8)
                    if len(extended) != 8:
                        raise FillError("invalid_video", "The MP4 contains a truncated extended atom.", exit_code=2)
                    atom_size = struct.unpack(">Q", extended)[0]
                    header_size = 16
                elif atom_size == 0:
                    atom_size = size_on_disk - offset
                if atom_size < header_size or offset + atom_size > size_on_disk:
                    raise FillError("invalid_video", "The MP4 contains an invalid atom size.", exit_code=2)
                if atom_type == b"mdat":
                    return moov_offset is not None
                if atom_type == b"moov" and moov_offset is None:
                    moov_offset = offset
                offset += atom_size
                handle.seek(offset)
    except FillError:
        raise
    except OSError as exc:
        raise FillError("media_unreadable", f"Cannot inspect MP4: {path}", exit_code=2) from exc
    raise FillError("invalid_video", "The MP4 has no top-level mdat atom.", exit_code=2)


def validate_media(video: Path, cover: Path) -> str:
    if video.suffix.lower() != ".mp4":
        raise FillError("invalid_video", "Video must be an .mp4 file.", exit_code=2)
    if not video.is_file() or video.stat().st_size == 0:
        raise FillError("invalid_video", f"Video does not exist or is empty: {video}", exit_code=2)
    if cover.suffix.lower() not in _IMAGE_SUFFIXES or not cover.is_file() or cover.stat().st_size == 0:
        raise FillError(
            "invalid_cover",
            "Cover must be a non-empty JPG, PNG, or WebP image.",
            exit_code=2,
        )
    if not mp4_faststart(video):
        raise FillError(
            "video_not_faststart",
            "MP4 moov metadata is after mdat. Remux without re-encoding, for example: "
            "ffmpeg -i input.mp4 -c copy -movflags +faststart output.mp4",
            exit_code=2,
        )
    return sha256_file(video)


def _selftest_atom(atom_type: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), atom_type) + payload
