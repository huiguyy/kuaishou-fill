from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import support  # noqa: F401
from fillup_core.errors import FillError
from fillup_core.page import close_date_picker, wait_for_upload


class EmptyPage:
    def __init__(self) -> None:
        self.keys: list[str] = []
        self.keyboard = self

    async def press(self, key: str) -> None:
        self.keys.append(key)

    async def wait_for_timeout(self, milliseconds: float) -> None:
        return None

    def locator(self, selector: str):
        return EmptyPanel()


class EmptyPanel:
    @property
    def last(self):
        return self

    async def count(self) -> int:
        return 0


class PageGuardTests(unittest.TestCase):
    def test_marker_free_page_never_counts_as_upload_complete(self) -> None:
        page = EmptyPage()
        with (
            patch("fillup_core.page.body_text", new=AsyncMock(return_value="")),
            patch("fillup_core.page._enabled_publish_control_exists", new=AsyncMock(return_value=True)),
            patch("fillup_core.page._media_preview_exists", new=AsyncMock(return_value=False)),
            self.assertRaises(FillError) as caught,
        ):
            asyncio.run(wait_for_upload(page, 0.003, platform="douyin", poll_interval=0.001))
        self.assertEqual(caught.exception.code, "upload_timeout")

    def test_reupload_label_without_media_preview_is_not_success(self) -> None:
        page = EmptyPage()
        with (
            patch("fillup_core.page.body_text", new=AsyncMock(return_value="重新上传")),
            patch("fillup_core.page._enabled_publish_control_exists", new=AsyncMock(return_value=True)),
            patch("fillup_core.page._media_preview_exists", new=AsyncMock(return_value=False)),
            self.assertRaises(FillError),
        ):
            asyncio.run(wait_for_upload(page, 0.003, platform="douyin", poll_interval=0.001))

    def test_persistent_uploading_is_not_success(self) -> None:
        page = EmptyPage()
        with (
            patch("fillup_core.page.body_text", new=AsyncMock(return_value="上传完成 重新上传 上传中")),
            patch("fillup_core.page._enabled_publish_control_exists", new=AsyncMock(return_value=True)),
            patch("fillup_core.page._media_preview_exists", new=AsyncMock(return_value=True)),
            self.assertRaises(FillError),
        ):
            asyncio.run(wait_for_upload(page, 0.003, platform="kuaishou", poll_interval=0.001))

    def test_positive_preview_marker_and_enabled_control_are_required(self) -> None:
        page = EmptyPage()
        with (
            patch("fillup_core.page.body_text", new=AsyncMock(return_value="上传完成")),
            patch("fillup_core.page._enabled_publish_control_exists", new=AsyncMock(return_value=True)),
            patch("fillup_core.page._media_preview_exists", new=AsyncMock(return_value=True)),
        ):
            asyncio.run(wait_for_upload(page, 0.01, platform="douyin", poll_interval=0.001))

    def test_date_picker_escape_has_no_enter(self) -> None:
        page = EmptyPage()
        asyncio.run(close_date_picker(page))
        self.assertEqual(page.keys, ["Escape"])


if __name__ == "__main__":
    unittest.main()
