from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import faststart_bytes
from fillup_core.contract import FillRequest
from fillup_core.errors import FillError
from fillup_core.runner import run_fill


class FakePage:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def screenshot(self, path: str, full_page: bool = False) -> None:
        self.events.append("screenshot")
        Path(path).write_bytes(b"local screenshot")


class FakeSession:
    def __init__(self, request: FillRequest, events: list[str]) -> None:
        self.request = request
        self.events = events
        self.page = FakePage(events)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        self.events.append("stop")

    def browser_info(self) -> dict:
        return {
            "left_open": not self.request.headless(),
            "headless": self.request.headless(),
            "history_recorded": not self.request.headless(),
        }


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / "video.mp4"
        self.video.write_bytes(faststart_bytes())
        self.cover = self.root / "cover.png"
        self.cover.write_bytes(b"cover")
        self.events: list[str] = []

    def tearDown(self) -> None:
        self.temp.cleanup()

    def request(self, headless: bool = False) -> FillRequest:
        return (
            FillRequest.builder("douyin")
            .with_media(self.video, self.cover)
            .with_metadata("title")
            .with_authentication(chrome_profile=self.root / "profile")
            .with_browser(headless=headless)
            .with_paths(evidence_root=self.root / "evidence", history_file=self.root / "history.json")
            .with_fill_only(True)
            .build()
        )

    def session_factory(self, request: FillRequest) -> FakeSession:
        return FakeSession(request, self.events)

    def test_failure_screenshot_precedes_disconnect_and_partial_fields_survive(self) -> None:
        async def failing_adapter(page, request, fields):
            fields.append("title")
            raise FillError("boom", "stop here")

        with patch("fillup_core.runner.ChromeSession", new=self.session_factory):
            result, code = run_fill(self.request(), failing_adapter)
        payload = result.to_dict()
        self.assertEqual(code, 4)
        self.assertTrue(payload["filled"])
        self.assertEqual(payload["evidence"]["fields"], ["title"])
        self.assertTrue(Path(payload["evidence"]["screenshot"]).is_file())
        self.assertEqual(self.events, ["screenshot", "stop"])

    def test_unexpected_failure_also_captures_screenshot(self) -> None:
        async def failing_adapter(page, request, fields):
            raise ValueError("synthetic")

        with patch("fillup_core.runner.ChromeSession", new=self.session_factory):
            result, code = run_fill(self.request(), failing_adapter)
        self.assertEqual(code, 5)
        self.assertEqual(result.to_dict()["error"]["code"], "internal_error")
        self.assertTrue(Path(result.to_dict()["evidence"]["screenshot"]).is_file())
        self.assertEqual(self.events, ["screenshot", "stop"])

    def test_headless_success_does_not_write_duplicate_history(self) -> None:
        async def successful_adapter(page, request, fields):
            fields.extend(["video", "title"])
            return fields

        with patch("fillup_core.runner.ChromeSession", new=self.session_factory):
            result, code = run_fill(self.request(headless=True), successful_adapter)
        self.assertEqual(code, 0)
        self.assertFalse(result.to_dict()["browser"]["left_open"])
        self.assertFalse(result.to_dict()["browser"]["history_recorded"])
        self.assertFalse((self.root / "history.json").exists())


if __name__ == "__main__":
    unittest.main()
