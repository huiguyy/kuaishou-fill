from __future__ import annotations

import asyncio
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

import support
from fillup_core.browser import find_chrome
from fillup_core.contract import FillRequest
from fillup_core.page import normalized_text

BASE_HTML = """<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>
<style>.hidden {{ display:none; }}</style></head><body><form onsubmit='publishTrap(); return false;'>{body}</form>
<script>
function show(id) {{ document.getElementById(id).classList.remove('hidden'); }}
function hide(id) {{ document.getElementById(id).classList.add('hidden'); }}
window.__published = false;
function publishTrap() {{ window.__published = true; }}
</script></body></html>"""

DOUYIN_BODY = """
<input class='upload-btn-input' type='file' accept='video/*'>
<input placeholder='填写作品标题'>
<div class='zone-container' contenteditable='true'></div>
<div class='long-card'><video controls></video></div><div>重新上传</div>
<button type='button' id='cover-open' onclick="show('cover-modal')">编辑封面</button>
<div id='cover-modal' class='dy-creator-content-modal hidden'>
  <button type='button'>设置竖封面</button>
  <div class='semi-upload'><span class='semi-upload-drag-area-main-text'>上传</span>
    <input class='semi-upload-hidden-input' type='file' accept='image/*'></div>
  <button type='button' onclick="hide('cover-modal')">完成</button>
</div>
<label class='radio' onclick="show('schedule')">定时发布</label>
<input id='schedule' class='semi-input hidden' placeholder='日期和时间'>
<button type='submit' onclick='publishTrap()'>发布</button>
"""

KUAISHOU_BODY = """
<input id='file' type='file' accept='video/*' class='hidden'>
<button type='button' class='_upload-btn-test' onclick="document.getElementById('file').click()">上传视频</button>
<div>描述</div><div contenteditable='true'></div>
<div class='progress-div'><video controls></video></div><div>重新上传</div>
<div><span>封面设置</span></div><div><div onclick="show('cover-modal')"><button type='button'>打开封面</button></div></div>
<div id='cover-modal' role='document' class='ant-modal hidden'>
  <button type='button'>上传封面</button><input type='file' accept='image/*'>
  <button type='button' onclick="hide('cover-modal')">确认</button>
</div>
<label class='ant-radio-wrapper' onclick="show('schedule')">定时发布</label>
<input id='schedule' class='hidden' placeholder='选择日期时间'>
<button type='submit' onclick='publishTrap()'>发布</button>
"""


def load_adapter(platform: str, path: Path):
    spec = importlib.util.spec_from_file_location(f"test_{platform}_adapter", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(os.environ.get("FILLUP_BROWSER_TEST") == "1", "set FILLUP_BROWSER_TEST=1 for isolated adapter browser tests")
class AdapterBrowserTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["FILLUP_PACE_SKIP"] = "1"

    def request(self, platform: str, root: Path) -> FillRequest:
        video = root / "video.mp4"
        video.write_bytes(support.faststart_bytes())
        cover = root / "cover.png"
        cover.write_bytes(b"local image")
        return (
            FillRequest.builder(platform)
            .with_media(video, cover)
            .with_metadata("集成标题", "集成正文", "甲,乙")
            .with_authentication(chrome_profile=root / "profile")
            .with_schedule("2099-01-02 03:04")
            .with_timeout(30)
            .with_fill_only(True)
            .build()
        )

    def run_adapter(self, platform: str, body: str, expected_schedule: str) -> None:
        async def scenario() -> None:
            from playwright.async_api import async_playwright
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                fixture = root / "fixture.html"
                fixture.write_text(BASE_HTML.format(title=platform, body=body), encoding="utf-8")
                adapter = load_adapter(platform, support.script_dir(platform) / f"{platform}_adapter.py")
                adapter.UPLOAD_URL = fixture.as_uri()
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True, executable_path=str(find_chrome(None)))
                    page = await browser.new_page()
                    fields = await getattr(adapter, f"fill_{platform}")(page, self.request(platform, root))
                    self.assertEqual(fields, ["video", "title", "description", "tags", "cover", "schedule"])
                    if platform == "douyin":
                        self.assertEqual(await page.locator('input[placeholder="填写作品标题"]').input_value(), "集成标题")
                    else:
                        self.assertIn("集成标题", await page.locator("body").inner_text())
                    self.assertIn("集成正文", await page.locator("body").inner_text())
                    self.assertIn("#甲", await page.locator("body").inner_text())
                    self.assertIn("#乙", await page.locator("body").inner_text())
                    editor_selector = ".zone-container" if platform == "douyin" else "div[contenteditable='true']"
                    expected_caption = "集成正文 #甲 #乙" if platform == "douyin" else "集成标题 集成正文 #甲 #乙"
                    self.assertEqual(normalized_text(await page.locator(editor_selector).inner_text()), expected_caption)
                    schedule = page.locator('input[placeholder="日期和时间"], input[placeholder="选择日期时间"]')
                    self.assertIn(expected_schedule, await schedule.input_value())
                    self.assertFalse(await page.evaluate("window.__published"))
                    await browser.close()
        asyncio.run(scenario())

    def test_douyin_adapter_fills_without_publish_event(self) -> None:
        if "douyin" not in support.platforms():
            self.skipTest("not the Douyin standalone repository")
        self.run_adapter("douyin", DOUYIN_BODY, "2099-01-02 03:04")

    def test_kuaishou_adapter_fills_without_publish_event(self) -> None:
        if "kuaishou" not in support.platforms():
            self.skipTest("not the Kuaishou standalone repository")
        self.run_adapter("kuaishou", KUAISHOU_BODY, "2099-01-02 03:04:00")


if __name__ == "__main__":
    unittest.main()
