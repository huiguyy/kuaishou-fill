from __future__ import annotations

import unittest
from pathlib import Path

import support  # noqa: F401 - installs the correct core path for workspace or standalone repo
from fillup_core.browser import _validate_dedicated_profile, validate_cdp_url
from fillup_core.errors import FillError


class BrowserValidationTests(unittest.TestCase):
    def test_only_loopback_cdp_is_accepted(self) -> None:
        self.assertEqual(validate_cdp_url("http://127.0.0.1:9222/"), "http://127.0.0.1:9222")
        for url in ("http://example.com:9222", "https://127.0.0.1:9222", "http://user:pass@127.0.0.1:9222", "http://127.0.0.1"):
            with self.subTest(url=url), self.assertRaises(FillError):
                validate_cdp_url(url)

    def test_everyday_default_profile_is_rejected(self) -> None:
        with self.assertRaises(FillError) as caught:
            _validate_dedicated_profile(Path.home() / "Library/Application Support/Google/Chrome")
        self.assertEqual(caught.exception.code, "dedicated_profile_required")


if __name__ == "__main__":
    unittest.main()
