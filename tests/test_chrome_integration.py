from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
import urllib.request
from pathlib import Path

import support  # noqa: F401 - installs the correct core path for workspace or standalone repo
from fillup_core.browser import ChromeSession
from fillup_core.contract import FillRequest


def request_for(root: Path, headless: bool) -> FillRequest:
    return (
        FillRequest.builder("douyin")
        .with_media(root / "unused.mp4", root / "unused.png")
        .with_metadata("local-only")
        .with_authentication(chrome_profile=root / "dedicated-profile")
        .with_browser(headless=headless)
        .with_fill_only(True)
        .build()
    )


def stop_process(process) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except Exception:
            process.kill()


@unittest.skipUnless(os.environ.get("FILLUP_BROWSER_TEST") == "1", "set FILLUP_BROWSER_TEST=1 for isolated Chrome lifecycle test")
class HeadlessChromeLifecycleTests(unittest.TestCase):
    def test_headless_chrome_is_disposable_after_disconnect(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            process = None

            async def scenario() -> None:
                nonlocal process
                async with ChromeSession(request_for(root, True)) as session:
                    process = session._process
                    await session.page.set_content("<title>fillup-local-only</title>")
                self.assertIsNotNone(process)
                self.assertIsNotNone(process.poll(), "headless Chrome remained alive after evidence capture")

            try:
                asyncio.run(scenario())
            finally:
                stop_process(process)


@unittest.skipUnless(os.environ.get("FILLUP_HEADED_BROWSER_TEST") == "1", "set FILLUP_HEADED_BROWSER_TEST=1 for headed lifecycle test")
class HeadedChromeLifecycleTests(unittest.TestCase):
    def test_external_chrome_and_filled_page_survive_disconnect(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            process = None

            async def scenario() -> list[dict]:
                nonlocal process
                async with ChromeSession(request_for(root, False)) as session:
                    process = session._process
                    await session.page.set_content("<title>fillup-local-only</title><p>no network</p>")
                    port = (root / "dedicated-profile" / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()[0]
                self.assertIsNotNone(process)
                self.assertIsNone(process.poll(), "disconnect closed the headed external Chrome process")
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as response:
                    return json.load(response)

            try:
                pages = asyncio.run(scenario())
                self.assertTrue(any(page.get("title") == "fillup-local-only" for page in pages))
            finally:
                stop_process(process)


if __name__ == "__main__":
    unittest.main()
