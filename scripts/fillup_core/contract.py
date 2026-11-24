"""Versioned input/output contracts for independently installable skills."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import FillError

CONTRACT_VERSION = 1
SCHEDULE_FORMAT = "%Y-%m-%d %H:%M"


def parse_tags(raw: str, platform: str) -> tuple[str, ...]:
    tags: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        tag = part.strip().lstrip("#").strip()
        if not tag or tag in seen:
            continue
        if any(ch in tag for ch in "\r\n,"):
            raise FillError("invalid_tags", "Each tag must be a single line without commas.", exit_code=2)
        if len(tag) > 50:
            raise FillError("invalid_tags", "Each tag must contain at most 50 characters.", exit_code=2)
        seen.add(tag)
        tags.append(tag)
    maximum = 3 if platform == "kuaishou" else 10
    if len(tags) > maximum:
        raise FillError(
            "invalid_tags",
            f"{platform} accepts at most {maximum} tags in this skill.",
            exit_code=2,
        )
    return tuple(tags)


def parse_schedule(raw: str | None, *, now: datetime | None = None) -> datetime | None:
    if not raw:
        return None
    try:
        naive = datetime.strptime(raw, SCHEDULE_FORMAT)
    except ValueError as exc:
        raise FillError(
            "invalid_schedule",
            "Schedule must use local time in YYYY-MM-DD HH:MM format.",
            exit_code=2,
        ) from exc
    current = now or datetime.now().astimezone()
    local_tz = current.tzinfo
    scheduled = naive.replace(tzinfo=local_tz)
    if scheduled <= current:
        raise FillError("invalid_schedule", "Schedule must be in the future.", exit_code=2)
    return scheduled


class FillRequest:
    """Private request fields; construct with :meth:`builder` and use readers."""

    __slots__ = (
        "_platform", "_video", "_cover", "_title", "_desc", "_tags",
        "_storage_state", "_chrome_profile", "_headless", "_schedule",
        "_evidence_root", "_history_file", "_chrome_path", "_cdp_url",
        "_timeout_seconds", "_fill_only",
    )

    def __init__(self, **values: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, values.get(name))

    @classmethod
    def builder(cls, platform: str) -> "FillRequestBuilder":
        return FillRequestBuilder(platform)

    def platform(self) -> str: return self._platform
    def video(self) -> Path: return self._video
    def cover(self) -> Path: return self._cover
    def title(self) -> str: return self._title
    def desc(self) -> str: return self._desc
    def tags(self) -> tuple[str, ...]: return self._tags
    def storage_state(self) -> Path | None: return self._storage_state
    def chrome_profile(self) -> Path: return self._chrome_profile
    def headless(self) -> bool: return self._headless
    def schedule(self) -> datetime | None: return self._schedule
    def schedule_text(self, *, seconds: bool = False) -> str | None:
        if self._schedule is None:
            return None
        fmt = "%Y-%m-%d %H:%M:%S" if seconds else SCHEDULE_FORMAT
        return self._schedule.strftime(fmt)
    def evidence_root(self) -> Path: return self._evidence_root
    def history_file(self) -> Path: return self._history_file
    def chrome_path(self) -> Path | None: return self._chrome_path
    def cdp_url(self) -> str | None: return self._cdp_url
    def timeout_seconds(self) -> int: return self._timeout_seconds
    def fill_only(self) -> bool: return self._fill_only

    def caption(self) -> str:
        return ((self._title + "\n") if self._title else "") + self._desc


class FillRequestBuilder:
    def __init__(self, platform: str) -> None:
        self._values: dict[str, Any] = {"_platform": platform}

    def with_media(self, video: str | Path, cover: str | Path) -> "FillRequestBuilder":
        self._values["_video"] = Path(video).expanduser().resolve()
        self._values["_cover"] = Path(cover).expanduser().resolve()
        return self

    def with_metadata(self, title: str, desc: str = "", tags: str = "") -> "FillRequestBuilder":
        self._values["_title"] = title.strip()
        self._values["_desc"] = desc.strip()
        self._values["_tags"] = parse_tags(tags, self._values["_platform"])
        return self

    def with_authentication(
        self,
        *,
        storage_state: str | Path | None = None,
        chrome_profile: str | Path | None = None,
    ) -> "FillRequestBuilder":
        self._values["_storage_state"] = (
            Path(storage_state).expanduser().resolve() if storage_state else None
        )
        self._values["_chrome_profile"] = (
            Path(chrome_profile).expanduser().resolve() if chrome_profile else None
        )
        return self

    def with_browser(
        self,
        *,
        headless: bool = False,
        chrome_path: str | Path | None = None,
        cdp_url: str | None = None,
    ) -> "FillRequestBuilder":
        self._values["_headless"] = bool(headless)
        self._values["_chrome_path"] = Path(chrome_path).expanduser().resolve() if chrome_path else None
        self._values["_cdp_url"] = cdp_url
        return self

    def with_schedule(self, schedule: str | None, *, now: datetime | None = None) -> "FillRequestBuilder":
        self._values["_schedule"] = parse_schedule(schedule, now=now)
        return self

    def with_paths(
        self,
        *,
        evidence_root: str | Path | None = None,
        history_file: str | Path | None = None,
    ) -> "FillRequestBuilder":
        self._values["_evidence_root"] = Path(evidence_root).expanduser().resolve() if evidence_root else None
        self._values["_history_file"] = Path(history_file).expanduser().resolve() if history_file else None
        return self

    def with_timeout(self, seconds: int) -> "FillRequestBuilder":
        self._values["_timeout_seconds"] = seconds
        return self

    def with_fill_only(self, enabled: bool) -> "FillRequestBuilder":
        self._values["_fill_only"] = enabled
        return self

    def build(self) -> FillRequest:
        platform = self._values.get("_platform")
        if platform not in {"douyin", "kuaishou"}:
            raise FillError("invalid_platform", "Platform must be douyin or kuaishou.", exit_code=2)
        home = Path.home() / ".fillup-skills"
        for key, default in (
            ("_chrome_profile", home / "chrome-profiles" / platform),
            ("_evidence_root", home / "evidence" / platform),
            ("_history_file", home / "history" / f"{platform}.json"),
        ):
            if self._values.get(key) is None:
                self._values[key] = default
        self._values.setdefault("_timeout_seconds", 480)
        self._values.setdefault("_headless", False)
        self._values.setdefault("_fill_only", False)
        self._values.setdefault("_schedule", None)
        self._values.setdefault("_storage_state", None)
        self._values.setdefault("_chrome_path", None)
        self._values.setdefault("_cdp_url", None)
        self._values.setdefault("_tags", ())
        self._values.setdefault("_desc", "")
        if not self._values["_fill_only"]:
            raise FillError(
                "fill_only_required",
                "Pass --fill-only. This skill intentionally has no submit option.",
                exit_code=2,
            )
        for key, label in (("_video", "video"), ("_cover", "cover")):
            if self._values.get(key) is None:
                raise FillError("invalid_arguments", f"A {label} path is required.", exit_code=2)
        if not self._values.get("_title"):
            raise FillError("invalid_title", "Title must not be empty.", exit_code=2)
        if not self._values["_storage_state"] and not self._values["_chrome_profile"]:
            raise FillError(
                "authentication_required",
                "Provide --storage-state or --chrome-profile; automatic login is not supported.",
                exit_code=2,
            )
        if not 30 <= self._values["_timeout_seconds"] <= 3600:
            raise FillError("invalid_timeout", "Timeout must be between 30 and 3600 seconds.", exit_code=2)
        title = self._values["_title"]
        desc = self._values["_desc"]
        tags = self._values["_tags"]
        inserted_tags_length = sum(len(tag) + 2 for tag in tags)
        if platform == "douyin":
            if len(title) > 30:
                raise FillError("invalid_title", "Douyin titles are limited to 30 characters.", exit_code=2)
            body_length = len(desc) + inserted_tags_length
            if body_length > 2000:
                raise FillError("invalid_description", "Douyin description plus tags exceeds 2000 characters.", exit_code=2)
        else:
            caption_length = len(title) + (1 if desc else 0) + len(desc) + inserted_tags_length
            if caption_length > 1000:
                raise FillError(
                    "invalid_description",
                    "Kuaishou title, description, tags, and inserted separators exceed 1000 characters.",
                    exit_code=2,
                )
        if self._values["_headless"] and self._values["_cdp_url"]:
            raise FillError("invalid_arguments", "--headless cannot be combined with --cdp-url.", exit_code=2)
        return FillRequest(**self._values)


class FillResult:
    """Single-line JSON result with no media text, cookies, or account identifiers."""

    def __init__(self, **values: Any) -> None:
        self._values = values

    @classmethod
    def filled(
        cls,
        platform: str,
        fields: list[str],
        screenshot: Path,
        browser: dict[str, Any],
    ) -> "FillResult":
        return cls(
            contract_version=CONTRACT_VERSION,
            platform=platform,
            ok=True,
            filled=True,
            skipped=False,
            submit="left_to_human",
            evidence={"fields": fields, "screenshot": str(screenshot)},
            browser=browser,
        )

    @classmethod
    def skipped(cls, platform: str, previous: dict[str, Any]) -> "FillResult":
        return cls(
            contract_version=CONTRACT_VERSION,
            platform=platform,
            ok=True,
            filled=False,
            skipped=True,
            reason="already_filled",
            submit="left_to_human",
            evidence={"fields": previous.get("fields", []), "screenshot": previous.get("screenshot", "")},
            message="This exact video was already filled on this platform; no browser action was repeated.",
        )

    @classmethod
    def failure(
        cls,
        platform: str,
        error: FillError,
        screenshot: str = "",
        *,
        filled: bool = False,
        fields: list[str] | None = None,
    ) -> "FillResult":
        return cls(
            contract_version=CONTRACT_VERSION,
            platform=platform,
            ok=False,
            filled=filled,
            skipped=False,
            submit="left_to_human",
            evidence={"fields": list(fields or []), "screenshot": screenshot},
            error=error.as_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        return dict(self._values)

    def to_json(self) -> str:
        return json.dumps(self._values, ensure_ascii=False, separators=(",", ":"))
