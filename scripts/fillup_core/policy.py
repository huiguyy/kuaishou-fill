"""Single fill-only click gate; platform adapters cannot opt into submission."""
from __future__ import annotations

import enum
import re
from typing import Any

from .errors import FillError


class Decision(enum.Enum):
    ALLOW = "allow"
    DENY = "deny"


SAFE_CLICK_INTENTS = frozenset({
    "focus_field",
    "choose_media",
    "open_cover",
    "select_cover_tab",
    "confirm_cover",
    "select_schedule",
    "confirm_schedule",
    "dismiss_overlay",
})


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def decide(intent: str, element_text: str = "") -> Decision:
    """Pure policy for every browser click in the skills."""
    if intent not in SAFE_CLICK_INTENTS:
        return Decision.DENY
    label = _normalize(element_text)
    if label.startswith(("确认发布", "提交发布", "立即发布")):
        return Decision.DENY
    if label in {"提交", "发表", "发表作品", "提交审核"}:
        return Decision.DENY
    if label.startswith("发布") and label != "定时发布":
        return Decision.DENY
    return Decision.ALLOW


async def guarded_click(locator: Any, *, intent: str, timeout: int = 8000) -> None:
    """Read the target label, authorize, then click; there is no submit intent."""
    try:
        text = await locator.inner_text(timeout=min(timeout, 2000))
    except Exception:
        text = ""
    if decide(intent, text) is not Decision.ALLOW:
        raise FillError(
            "fill_only_guard",
            f"Blocked a click outside the fill-only allowlist (intent={intent!r}). "
            "No submit or publish action is available.",
            exit_code=6,
        )
    try:
        await locator.click(timeout=timeout)
    except Exception as exc:
        raise FillError(
            "element_click_failed",
            f"Could not perform safe browser action {intent!r}: {exc.__class__.__name__}",
            retryable=True,
        ) from exc
