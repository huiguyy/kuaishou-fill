"""Kuaishou form shell adapted from SAU's proven ordering, without submit paths."""
from __future__ import annotations

from typing import Any

from fillup_core.contract import FillRequest
from fillup_core.errors import FillError
from fillup_core.page import (
    append_tags,
    check_account_state,
    close_date_picker,
    dismiss_known_overlay,
    fill_rich_text,
    require_visible,
    wait_for_upload,
)
from fillup_core.pace import apace
from fillup_core.policy import guarded_click

UPLOAD_URL = "https://cp.kuaishou.com/article/publish/video"


async def _set_video(page: Any, request: FillRequest) -> None:
    upload_button = await require_visible(
        page,
        ("button[class^='_upload-btn']", 'button:has-text("上传视频")', '[role="button"]:has-text("上传视频")'),
        "video upload button",
        timeout=10000,
    )
    try:
        async with page.expect_file_chooser(timeout=10000) as chooser_info:
            await guarded_click(upload_button, intent="choose_media")
        chooser = await chooser_info.value
        await chooser.set_files(str(request.video()), timeout=60000)
    except FillError:
        raise
    except Exception as exc:
        raise FillError("upload_failed", f"Could not attach the video: {exc.__class__.__name__}", retryable=True) from exc


async def _description_editor(page: Any, timeout_seconds: int) -> Any:
    label = page.get_by_text("描述", exact=False)
    candidates = [
        label.locator("xpath=following-sibling::div").first,
        label.locator("xpath=following::div[@contenteditable='true'][1]").first,
        label.locator("xpath=following::*[@contenteditable='true'][1]").first,
        page.locator('div[contenteditable="true"]').first,
    ]
    per_candidate = min(60_000, max(10_000, timeout_seconds * 250))
    for locator in candidates:
        try:
            await locator.wait_for(state="visible", timeout=per_candidate)
            return locator
        except Exception:
            continue
    raise FillError(
        "editor_not_found",
        "Kuaishou's description editor did not appear after media selection.",
        retryable=True,
    )


async def _set_cover(page: Any, request: FillRequest) -> None:
    cover_label = page.locator("span").filter(has_text="封面设置").first
    try:
        await cover_label.wait_for(state="visible", timeout=15000)
        opener = cover_label.locator("xpath=../following-sibling::div[1]").locator("div").nth(0)
        await guarded_click(opener, intent="open_cover", timeout=10000)
    except FillError:
        raise
    except Exception as exc:
        raise FillError("cover_control_not_found", "Could not open Kuaishou's cover editor.", retryable=True) from exc
    modal = await require_visible(page, ('div[role="document"].ant-modal',), "cover dialog", timeout=15000)
    upload_tab = modal.get_by_text("上传封面", exact=True).first
    await upload_tab.wait_for(state="visible", timeout=10000)
    await guarded_click(upload_tab, intent="select_cover_tab")
    cover_input = modal.locator('input[type="file"]').first
    await cover_input.wait_for(state="attached", timeout=15000)
    await cover_input.set_input_files(str(request.cover()), timeout=60000)
    confirm = modal.get_by_role("button", name="确认", exact=True).first
    await confirm.wait_for(state="visible", timeout=15000)
    await guarded_click(confirm, intent="confirm_cover")
    try:
        await modal.wait_for(state="hidden", timeout=30000)
    except Exception as exc:
        raise FillError("cover_dialog_open", "The Kuaishou cover dialog did not close.", retryable=True) from exc


async def _set_schedule(page: Any, request: FillRequest) -> None:
    schedule = request.schedule_text(seconds=True)
    if not schedule:
        return
    radio = await require_visible(page, ("label.ant-radio-wrapper:has-text('定时发布')",), "schedule radio")
    await guarded_click(radio, intent="select_schedule")
    date_input = await require_visible(page, ('input[placeholder="选择日期时间"]',), "schedule input")
    await guarded_click(date_input, intent="select_schedule")
    ok = await page.evaluate(
        """newValue => {
            const input = document.querySelector('input[placeholder="选择日期时间"]');
            if (!input) return false;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, newValue);
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }""",
        schedule,
    )
    if not ok:
        raise FillError("field_fill_failed", "Could not set Kuaishou's schedule input.")
    await close_date_picker(page)
    await page.wait_for_timeout(800)
    value = await date_input.input_value()
    if schedule not in value:
        raise FillError("field_verify_failed", f"Schedule did not persist: expected {schedule}.")


async def fill_kuaishou(page: Any, request: FillRequest, fields: list[str] | None = None) -> list[str]:
    if fields is None:
        fields = []
    await page.goto(UPLOAD_URL, wait_until="load", timeout=90000)
    await apace("task-switch")
    await check_account_state(page, "kuaishou")
    await _set_video(page, request)
    await dismiss_known_overlay(page)
    editor = await _description_editor(page, request.timeout_seconds())
    caption = request.caption().strip()
    await fill_rich_text(page, editor, caption, "title and description")
    fields.extend(["title"] + (["description"] if request.desc() else []))
    if request.tags():
        await append_tags(page, editor, request.tags(), caption)
        fields.append("tags")
    if len(await editor.inner_text()) > 1000:
        raise FillError("field_verify_failed", "Final Kuaishou caption including tags exceeds 1000 characters.")
    await wait_for_upload(page, request.timeout_seconds(), platform="kuaishou")
    fields.insert(0, "video")
    await dismiss_known_overlay(page)
    await _set_cover(page, request)
    fields.append("cover")
    if request.schedule():
        await _set_schedule(page, request)
        fields.append("schedule")
    await check_account_state(page, "kuaishou")
    return fields
