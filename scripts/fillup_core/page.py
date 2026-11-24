"""Playwright helpers with field verification and honest failure messages."""
from __future__ import annotations

import math
import sys
from typing import Any, Iterable

from .errors import FillError
from .policy import guarded_click

_LOGIN_MARKERS = (
    "扫码登录", "验证码登录", "密码登录", "手机号登录", "创作者登录", "立即登录",
)
_MANUAL_MARKERS = (
    "接收短信验证码", "为确保是本人操作", "输入验证码", "安全验证", "身份验证", "拖动滑块",
)
_COMPLETION_MARKERS = ("上传完成", "上传成功", "重新上传", "更换视频")


def normalized_text(text: str) -> str:
    return " ".join((text or "").replace("\xa0", " ").split())


async def body_text(page: Any, *, limit: int = 12000) -> str:
    try:
        return (await page.inner_text("body", timeout=5000))[:limit]
    except Exception:
        return ""


async def check_account_state(page: Any, platform: str) -> None:
    text = await body_text(page, limit=5000)
    if "passport." in page.url or "/login" in page.url or any(marker in text for marker in _LOGIN_MARKERS):
        raise FillError(
            "logged_out",
            f"{platform} is not logged in. Open the dedicated Chrome profile, sign in manually, "
            "and rerun; this skill never performs login or account recovery.",
            exit_code=3,
        )
    if any(marker in text for marker in _MANUAL_MARKERS):
        raise FillError(
            "manual_intervention_required",
            f"{platform} is asking for manual identity verification. Complete it in the open Chrome "
            "window and rerun. The skill does not automate verification challenges.",
            exit_code=3,
        )


async def first_visible(page: Any, selectors: Iterable[str], *, timeout: int = 2500) -> Any | None:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            return locator
        except Exception:
            continue
    return None


async def require_visible(page: Any, selectors: Iterable[str], field: str, *, timeout: int = 10000) -> Any:
    locator = await first_visible(page, selectors, timeout=timeout)
    if locator is None:
        raise FillError(
            "selector_not_found",
            f"Could not find the visible {field} control. The platform layout may have changed; "
            "inspect the evidence screenshot before updating selectors.",
            retryable=True,
        )
    return locator


async def fill_input(page: Any, selectors: Iterable[str], text: str, field: str) -> Any:
    locator = await require_visible(page, selectors, field)
    try:
        await locator.fill(text, timeout=8000)
    except Exception as exc:
        raise FillError("field_fill_failed", f"Could not fill {field}: {exc.__class__.__name__}", retryable=True) from exc
    value = await locator.input_value()
    if normalized_text(value) != normalized_text(text):
        raise FillError("field_verify_failed", f"The {field} value did not survive browser verification.")
    return locator


async def fill_rich_text(page: Any, locator: Any, text: str, field: str) -> None:
    await guarded_click(locator, intent="focus_field")
    shortcut = "Meta+A" if sys.platform == "darwin" else "Control+A"
    try:
        await locator.fill(text, timeout=5000)
    except Exception:
        await page.keyboard.press(shortcut)
        await page.keyboard.press("Delete")
        if text:
            await page.keyboard.insert_text(text)
    if normalized_text(await locator.inner_text()) != normalized_text(text):
        raise FillError("field_verify_failed", f"The {field} value did not exactly match browser verification.")


async def _focus_end(locator: Any) -> None:
    await locator.evaluate(
        """el => {
            el.focus();
            const range = document.createRange();
            range.selectNodeContents(el);
            range.collapse(false);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
        }"""
    )


async def append_tags(page: Any, locator: Any, tags: tuple[str, ...], expected_caption: str) -> None:
    for tag in tags:
        await _focus_end(locator)
        await page.keyboard.insert_text(f" #{tag} ")
        await page.wait_for_timeout(500)
    if tags:
        await page.keyboard.press("Escape")
        expected = normalized_text(expected_caption + " " + " ".join(f"#{tag}" for tag in tags))
        actual = normalized_text(await locator.inner_text())
        if actual != expected:
            raise FillError(
                "field_verify_failed",
                "Final caption/tags do not exactly match the requested text and order; possible caret displacement.",
            )


async def _enabled_publish_control_exists(page: Any) -> bool:
    """Read-only readiness signal; this function never clicks the control."""
    for label in ("发布", "发布作品"):
        locator = page.get_by_role("button", name=label, exact=True).last
        try:
            if await locator.count() and await locator.is_visible() and await locator.is_enabled():
                return True
        except Exception:
            continue
    return False


async def _media_preview_exists(page: Any, platform: str) -> bool:
    selectors = {
        "douyin": ("[class^='long-card'] video", "[class^='long-card'] img", "video"),
        "kuaishou": (".progress-div video", ".progress-div img", "video"),
    }
    for selector in selectors[platform]:
        preview = page.locator(selector).first
        try:
            if await preview.count() and await preview.is_visible():
                return True
        except Exception:
            continue
    return False


async def wait_for_upload(page: Any, timeout_seconds: int, *, platform: str, poll_interval: float = 2.0) -> None:
    """Require stable completion text, media preview, and an enabled final control."""
    stable = 0
    iterations = max(1, math.ceil(timeout_seconds / poll_interval))
    for _ in range(iterations):
        text = await body_text(page)
        if any(marker in text for marker in ("上传失败", "上传错误")):
            raise FillError(
                "upload_failed",
                f"{platform} reported an upload failure. No automatic retry or publish click was attempted.",
                retryable=True,
            )
        uploading = any(marker in text for marker in ("上传中", "正在上传", "转码中"))
        positive_marker = any(marker in text for marker in _COMPLETION_MARKERS)
        enabled = await _enabled_publish_control_exists(page)
        preview = await _media_preview_exists(page, platform)
        stable = stable + 1 if positive_marker and enabled and preview and not uploading else 0
        if stable >= 3:
            return
        await page.wait_for_timeout(poll_interval * 1000)
    raise FillError(
        "upload_timeout",
        f"Upload lacked stable completion text, a media preview, and an enabled final control within "
        f"{timeout_seconds} seconds. The browser remains open; no publish action was attempted.",
        retryable=True,
    )


async def close_date_picker(page: Any) -> None:
    """Confirm a picker-scoped safe button, or Escape; never implicit-submit with Enter."""
    for selector in (".semi-datepicker-panel", ".ant-picker-dropdown", '[role="dialog"]'):
        panel = page.locator(selector).last
        try:
            if not await panel.count() or not await panel.is_visible():
                continue
            for label in ("确定", "确认", "完成"):
                button = panel.get_by_role("button", name=label, exact=True).first
                if await button.count() and await button.is_visible():
                    await guarded_click(button, intent="confirm_schedule")
                    return
        except FillError:
            raise
        except Exception:
            continue
    await page.keyboard.press("Escape")


async def dismiss_known_overlay(page: Any) -> None:
    for label in ("我知道了", "跳过", "关闭"):
        locator = page.get_by_role("button", name=label, exact=True).first
        try:
            if await locator.count() and await locator.is_visible():
                await guarded_click(locator, intent="dismiss_overlay", timeout=2500)
        except FillError:
            raise
        except Exception:
            continue
