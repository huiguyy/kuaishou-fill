"""Shared execution pipeline: validate -> dedupe -> fill -> evidence -> mark."""
from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from .browser import ChromeSession
from .contract import FillRequest, FillResult
from .errors import FillError, clean_error_message
from .history import FillHistory
from .media import validate_media
from .pace import apace

Adapter = Callable[[Any, FillRequest, list[str]], Awaitable[list[str]]]


def _log(message: str) -> None:
    print(f"[fillup] {message}", file=sys.stderr, flush=True)


def _evidence_dir(request: FillRequest) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = request.evidence_root() / f"{stamp}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    return path


def _write_receipt(path: Path, result: FillResult) -> None:
    receipt = path / "receipt.json"
    try:
        receipt.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        receipt.chmod(0o600)
    except OSError as exc:
        _log(f"receipt write failed: {exc.__class__.__name__}")


async def _capture_failure(page: Any, evidence: Path) -> str:
    try:
        failure_shot = evidence / "failure.png"
        await page.screenshot(path=str(failure_shot), full_page=True)
        return str(failure_shot)
    except Exception:
        return ""


async def _execute(request: FillRequest, adapter: Adapter) -> tuple[FillResult, int]:
    video_hash = validate_media(request.video(), request.cover())
    history = FillHistory(request.history_file(), request.platform())
    previous = history.find(video_hash)
    if previous:
        return FillResult.skipped(request.platform(), previous), 0

    evidence = _evidence_dir(request)
    screenshot = evidence / "filled.png"
    fields: list[str] = []
    failure_screenshots: list[str] = []
    try:
        _log(f"validated media; opening {request.platform()} in fill-only mode")
        async with ChromeSession(request) as active:
            try:
                await adapter(active.page, request, fields)
                await apace("review", len(request.desc()))
                await active.page.screenshot(path=str(screenshot), full_page=True)
                browser = active.browser_info()
            except Exception:
                failure_screenshots.append(await _capture_failure(active.page, evidence))
                raise
        if not request.headless():
            history.mark(video_hash, fields, screenshot)
        result = FillResult.filled(request.platform(), fields, screenshot, browser)
        _write_receipt(evidence, result)
        if request.headless():
            _log("disposable headless evidence captured; Chrome closed; no duplicate marker written")
        else:
            _log("form filled and verified; Chrome left open before submission")
        return result, 0
    except FillError as exc:
        screenshot_value = next((path for path in reversed(failure_screenshots) if path), "")
        if not screenshot_value and fields and screenshot.exists():
            screenshot_value = str(screenshot)
        result = FillResult.failure(
            request.platform(), exc, screenshot_value, filled=bool(fields), fields=fields,
        )
        _write_receipt(evidence, result)
        _log(f"stopped: {exc.code}: {exc.message}")
        return result, exc.exit_code
    except Exception as exc:
        wrapped = FillError(
            "internal_error",
            f"Unexpected {exc.__class__.__name__}: {clean_error_message(exc)}. "
            "No submit action was requested; inspect the browser before retrying.",
            exit_code=5,
        )
        screenshot_value = next((path for path in reversed(failure_screenshots) if path), "")
        result = FillResult.failure(
            request.platform(), wrapped, screenshot_value, filled=bool(fields), fields=fields,
        )
        _write_receipt(evidence, result)
        _log(f"stopped: {wrapped.code}: {wrapped.message}")
        return result, wrapped.exit_code


def run_fill(request: FillRequest, adapter: Adapter) -> tuple[FillResult, int]:
    try:
        return asyncio.run(_execute(request, adapter))
    except FillError as exc:
        return FillResult.failure(request.platform(), exc), exc.exit_code
    except Exception as exc:
        wrapped = FillError("internal_error", f"Unexpected {exc.__class__.__name__}: {clean_error_message(exc)}", exit_code=5)
        return FillResult.failure(request.platform(), wrapped), wrapped.exit_code
