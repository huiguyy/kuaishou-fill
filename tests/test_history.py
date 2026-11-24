from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401 - installs the correct core path for workspace or standalone repo
from fillup_core.errors import FillError
from fillup_core.history import FillHistory


class HistoryTests(unittest.TestCase):
    def test_single_file_duplicate_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "nested" / "history.json"
            history = FillHistory(path, "douyin")
            self.assertIsNone(history.find("a" * 64))
            history.mark("a" * 64, ["video", "title"], Path(temp) / "shot.png")
            self.assertEqual(history.find("a" * 64)["platform"], "douyin")
            other = FillHistory(path, "kuaishou")
            self.assertIsNone(other.find("a" * 64))
            other.mark("a" * 64, ["video"], Path(temp) / "ks-shot.png")
            self.assertIsNotNone(history.find("a" * 64), "second platform overwrote the first marker")
            self.assertIsNotNone(other.find("a" * 64))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("title text", path.read_text(encoding="utf-8"))
            self.assertEqual(data["entries"]["douyin:" + "a" * 64]["fields"], ["video", "title"])

    def test_invalid_history_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "history.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaises(FillError) as caught:
                FillHistory(path, "douyin").find("a" * 64)
            self.assertEqual(caught.exception.code, "history_invalid")


if __name__ == "__main__":
    unittest.main()
