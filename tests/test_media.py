from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from support import atom, faststart_bytes
from fillup_core.errors import FillError
from fillup_core.media import mp4_faststart, sha256_file, validate_media


class MediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, data: bytes) -> Path:
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_moov_before_mdat_is_faststart(self) -> None:
        self.assertTrue(mp4_faststart(self.write("ok.mp4", faststart_bytes())))

    def test_moov_after_mdat_is_rejected_before_browser(self) -> None:
        video = self.write("slow.mp4", atom(b"ftyp", b"isom") + atom(b"mdat") + atom(b"moov"))
        cover = self.write("cover.png", b"cover")
        with self.assertRaises(FillError) as caught:
            validate_media(video, cover)
        self.assertEqual(caught.exception.code, "video_not_faststart")
        self.assertIn("ffmpeg", caught.exception.message)

    def test_truncated_extended_atom_is_rejected(self) -> None:
        path = self.write("bad.mp4", b"\x00\x00\x00\x01ftyp")
        with self.assertRaises(FillError) as caught:
            mp4_faststart(path)
        self.assertEqual(caught.exception.code, "invalid_video")

    def test_zero_size_atom_extends_to_eof(self) -> None:
        data = atom(b"moov") + b"\x00\x00\x00\x00mdatpayload"
        self.assertTrue(mp4_faststart(self.write("zero.mp4", data)))

    def test_sha256_is_stable(self) -> None:
        path = self.write("ok.mp4", faststart_bytes())
        self.assertEqual(sha256_file(path), sha256_file(path))
        self.assertEqual(len(sha256_file(path)), 64)


if __name__ == "__main__":
    unittest.main()
