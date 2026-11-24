from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from support import cli_path, faststart_bytes, platforms
from fillup_core.contract import FillRequest, FillResult, parse_schedule, parse_tags
from fillup_core.errors import FillError


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / "video.mp4"
        self.video.write_bytes(faststart_bytes())
        self.cover = self.root / "cover.png"
        self.cover.write_bytes(b"cover")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request(self, platform: str = "douyin") -> FillRequest:
        return (
            FillRequest.builder(platform)
            .with_media(self.video, self.cover)
            .with_metadata("title", "desc", "one,#two,one")
            .with_authentication()
            .with_browser()
            .with_paths(evidence_root=self.root / "evidence", history_file=self.root / "history.json")
            .with_timeout(480)
            .with_fill_only(True)
            .build()
        )

    def test_builder_defaults_are_real_paths_after_explicit_empty_auth(self) -> None:
        request = self.request()
        self.assertTrue(str(request.chrome_profile()).endswith("chrome-profiles/douyin"))
        self.assertEqual(request.tags(), ("one", "two"))
        self.assertFalse(request.headless())

    def test_fill_only_is_mandatory(self) -> None:
        with self.assertRaises(FillError) as caught:
            FillRequest.builder("douyin").with_media(self.video, self.cover).with_metadata("title").build()
        self.assertEqual(caught.exception.code, "fill_only_required")

    def test_schedule_validation(self) -> None:
        now = datetime(2026, 11, 24, 8, 0, tzinfo=timezone.utc)
        self.assertEqual(parse_schedule("2026-11-24 09:30", now=now).minute, 30)
        with self.assertRaises(FillError):
            parse_schedule("2026-11-24 07:59", now=now)
        with self.assertRaises(FillError):
            parse_schedule("tomorrow", now=now)

    def test_kuaishou_tag_limit(self) -> None:
        self.assertEqual(len(parse_tags("a,b,c", "kuaishou")), 3)
        with self.assertRaises(FillError):
            parse_tags("a,b,c,d", "kuaishou")

    def test_json_does_not_contain_user_content_or_secrets(self) -> None:
        result = FillResult.failure("douyin", FillError("x", "safe")).to_json()
        self.assertNotIn("title", json.loads(result).get("evidence", {}))
        self.assertNotIn("cookie", result.lower())

    def test_kuaishou_validation_includes_tags_and_separators(self) -> None:
        with self.assertRaises(FillError) as caught:
            (
                FillRequest.builder("kuaishou")
                .with_media(self.video, self.cover)
                .with_metadata("x" * 1000, "", "a")
                .with_fill_only(True)
                .build()
            )
        self.assertEqual(caught.exception.code, "invalid_description")
        request = (
            FillRequest.builder("kuaishou")
            .with_media(self.video, self.cover)
            .with_metadata("x" * 997, "", "a")
            .with_fill_only(True)
            .build()
        )
        self.assertEqual(len(request.title()), 997)

    def test_partial_failure_preserves_filled_fields(self) -> None:
        payload = FillResult.failure(
            "douyin", FillError("boom", "stopped"), filled=True, fields=["title"],
        ).to_dict()
        self.assertTrue(payload["filled"])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["evidence"]["fields"], ["title"])

    def test_help_needs_no_third_party_import(self) -> None:
        for platform in platforms():
            completed = subprocess.run(
                [sys.executable, "-I", "-B", "-S", str(cli_path(platform)), "--help"],
                text=True, capture_output=True, timeout=20, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("--fill-only", completed.stdout)
            self.assertNotIn("--submit", completed.stdout)

    def test_invalid_faststart_returns_one_json_object_without_browser(self) -> None:
        self.video.write_bytes(b"\x00\x00\x00\x08mdat" + b"\x00\x00\x00\x08moov")
        for platform in platforms():
            completed = subprocess.run(
                [sys.executable, "-I", "-B", str(cli_path(platform)),
                 "--video", str(self.video), "--cover", str(self.cover), "--title", "title",
                 "--chrome-profile", str(self.root / platform), "--evidence-dir", str(self.root / "evidence"),
                 "--history-file", str(self.root / f"{platform}.json"), "--fill-only"],
                text=True, capture_output=True, timeout=20, check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "video_not_faststart")
            self.assertEqual(payload["submit"], "left_to_human")
            self.assertEqual(len(completed.stdout.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
