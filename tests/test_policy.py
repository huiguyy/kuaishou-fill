from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT
from fillup_core.errors import FillError
from fillup_core.policy import Decision, decide, guarded_click


class FakeLocator:
    def __init__(self, text: str) -> None:
        self.text = text
        self.clicks = 0

    async def inner_text(self, timeout: int = 0) -> str:
        return self.text

    async def click(self, timeout: int = 0) -> None:
        self.clicks += 1


class PolicyTests(unittest.TestCase):
    def test_publish_labels_are_denied(self) -> None:
        for label in ("发布", "立即发布", "确认发布", "发布作品", "提交", "提交发布"):
            self.assertIs(decide("focus_field", label), Decision.DENY, label)
        self.assertIs(decide("unknown", "harmless"), Decision.DENY)

    def test_safe_controls_are_allowed(self) -> None:
        for label in ("定时发布", "完成", "确认", "上传封面", "上传视频"):
            self.assertIs(decide("select_schedule" if label == "定时发布" else "confirm_cover", label), Decision.ALLOW)

    def test_guard_blocks_before_click(self) -> None:
        locator = FakeLocator("确认发布")
        with self.assertRaises(FillError) as caught:
            asyncio.run(guarded_click(locator, intent="confirm_cover"))
        self.assertEqual(caught.exception.code, "fill_only_guard")
        self.assertEqual(locator.clicks, 0)

    def test_guard_allows_safe_click(self) -> None:
        locator = FakeLocator("定时发布")
        asyncio.run(guarded_click(locator, intent="select_schedule"))
        self.assertEqual(locator.clicks, 1)

    def test_static_gate_accepts_current_tree(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-I", str(ROOT / "tools" / "check_fill_only.py"), "--root", str(ROOT)],
            text=True, capture_output=True, timeout=20, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_static_gate_fails_on_deliberately_unsafe_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "bad_adapter.py").write_text("async def bad(page):\n    await page.click('发布')\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-I", str(ROOT / "tools" / "check_fill_only.py"), "--root", str(root)],
                text=True, capture_output=True, timeout=20, check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("bypasses guarded_click", completed.stderr)

    def test_static_gate_fails_on_implicit_enter_submission(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "bad_adapter.py").write_text(
                "async def bad(page):\n    await page.keyboard.press('Enter')\n", encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, "-I", str(ROOT / "tools" / "check_fill_only.py"), "--root", str(root)],
                text=True, capture_output=True, timeout=20, check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("implicitly submit", completed.stderr)


if __name__ == "__main__":
    unittest.main()
