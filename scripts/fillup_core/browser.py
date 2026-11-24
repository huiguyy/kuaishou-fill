"""Dedicated Chrome lifecycle: connect, fill, disconnect, leave Chrome open."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .contract import FillRequest
from .errors import FillError, clean_error_message

_PLATFORM_ORIGINS = {
    "douyin": "https://creator.douyin.com/",
    "kuaishou": "https://cp.kuaishou.com/",
}


def validate_cdp_url(raw: str) -> str:
    parsed = urlsplit(raw)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or parsed.port is None
    ):
        raise FillError(
            "invalid_cdp_url",
            "--cdp-url must be an http URL on 127.0.0.1, localhost, or ::1 with an explicit port.",
            exit_code=2,
        )
    return raw.rstrip("/")


def _default_profiles() -> set[Path]:
    home = Path.home()
    candidates = {
        home / ".config/google-chrome",
        home / ".config/chromium",
        home / "Library/Application Support/Google/Chrome",
        home / "Library/Application Support/Chromium",
    }
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.add(Path(local) / "Google/Chrome/User Data")
    return {path.expanduser() for path in candidates}


def _validate_dedicated_profile(path: Path) -> None:
    resolved = path.expanduser().resolve()
    for default in _default_profiles():
        if resolved == default or resolved == default / "Default":
            raise FillError(
                "dedicated_profile_required",
                "Refusing to automate Chrome's everyday Default profile. Use a separate --chrome-profile.",
                exit_code=2,
            )


def _chrome_candidates() -> list[Path]:
    names = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"]
    paths = [Path(found) for name in names if (found := shutil.which(name))]
    if sys.platform == "darwin":
        paths.extend([
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ])
    if os.name == "nt":
        for root_name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            root = os.environ.get(root_name)
            if root:
                paths.append(Path(root) / "Google/Chrome/Application/chrome.exe")
    return paths


def find_chrome(explicit: Path | None, playwright_executable: str | None = None) -> Path:
    candidates = ([explicit] if explicit else []) + _chrome_candidates()
    if playwright_executable:
        candidates.append(Path(playwright_executable))
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FillError(
        "chrome_not_found",
        "Chrome/Chromium was not found. Pass --chrome-path or run: python -m playwright install chromium",
        exit_code=3,
    )


def _storage_state(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            raise FillError("invalid_storage_state", "Storage-state file exceeds 10 MiB.", exit_code=2)
        data = json.loads(path.read_text(encoding="utf-8"))
    except FillError:
        raise
    except (OSError, ValueError) as exc:
        raise FillError(
            "invalid_storage_state",
            f"Storage-state file is missing or invalid JSON: {path}",
            exit_code=2,
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("cookies", []), list) or not isinstance(data.get("origins", []), list):
        raise FillError("invalid_storage_state", "Storage state must contain cookie and origin arrays.", exit_code=2)
    return data


class ChromeSession:
    def __init__(self, request: FillRequest) -> None:
        self._request = request
        self._playwright: Any = None
        self._browser: Any = None
        self._process: subprocess.Popen[Any] | None = None
        self._mode = "attached_existing"
        self.page: Any = None

    async def __aenter__(self) -> "ChromeSession":
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise FillError(
                "dependency_missing",
                "Playwright is required only for execution: python -m pip install -r requirements.txt",
                exit_code=3,
            ) from exc
        self._playwright = await async_playwright().start()
        try:
            cdp_url = validate_cdp_url(self._request.cdp_url()) if self._request.cdp_url() else self._launch_chrome()
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            if not self._browser.contexts:
                raise FillError("browser_context_missing", "The dedicated Chrome has no default browser context.", exit_code=3)
            context = self._browser.contexts[0]
            self.page = await context.new_page()
            await self._import_state(context, self.page)
            return self
        except FillError:
            await self._disconnect()
            raise
        except Exception as exc:
            await self._disconnect()
            raise FillError(
                "browser_connection_failed",
                f"Could not connect to the dedicated Chrome: {clean_error_message(exc)}",
                exit_code=3,
                retryable=True,
            ) from exc

    def _launch_chrome(self) -> str:
        profile = self._request.chrome_profile()
        _validate_dedicated_profile(profile)
        executable = find_chrome(
            self._request.chrome_path(),
            getattr(self._playwright.chromium, "executable_path", None),
        )
        try:
            profile.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            raise FillError("profile_unwritable", f"Cannot create Chrome profile: {profile}", exit_code=2) from exc
        args = [
            str(executable),
            f"--user-data-dir={profile}",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-session-crashed-bubble",
            "about:blank",
        ]
        if self._request.headless():
            args.insert(1, "--headless=new")
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        else:
            popen_kwargs["start_new_session"] = True
        try:
            self._process = subprocess.Popen(args, **popen_kwargs)
        except OSError as exc:
            raise FillError("browser_launch_failed", f"Could not launch Chrome: {exc}", exit_code=3) from exc
        self._mode = "dedicated_profile"
        port_file = profile / "DevToolsActivePort"
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                lines = port_file.read_text(encoding="utf-8").splitlines()
                if lines and lines[0].strip().isdigit():
                    return f"http://127.0.0.1:{lines[0].strip()}"
            except OSError:
                pass
            if self._process.poll() is not None and not port_file.exists():
                break
            time.sleep(0.1)
        raise FillError(
            "browser_debug_port_missing",
            "Chrome did not expose a local debugging port. Close other windows using this dedicated "
            "profile, or start Chrome with remote debugging and pass --cdp-url.",
            exit_code=3,
            retryable=True,
        )

    async def _import_state(self, context: Any, page: Any) -> None:
        path = self._request.storage_state()
        if not path:
            return
        state = _storage_state(path)
        cookies = state.get("cookies", [])
        if cookies:
            try:
                await context.add_cookies(cookies)
            except Exception as exc:
                raise FillError("invalid_storage_state", f"Chrome rejected the supplied cookies: {exc.__class__.__name__}", exit_code=2) from exc
        expected_origin = _PLATFORM_ORIGINS[self._request.platform()].rstrip("/")
        entries: list[dict[str, str]] = []
        for origin in state.get("origins", []):
            if origin.get("origin", "").rstrip("/") == expected_origin:
                entries.extend(origin.get("localStorage", []))
        if entries:
            await page.goto(expected_origin, wait_until="domcontentloaded", timeout=90000)
            try:
                await page.evaluate(
                    "items => { for (const item of items) localStorage.setItem(item.name, item.value); }",
                    [{"name": str(item["name"]), "value": str(item["value"])} for item in entries],
                )
            except Exception as exc:
                raise FillError("invalid_storage_state", "Could not import platform localStorage state.", exit_code=2) from exc

    def browser_info(self) -> dict[str, Any]:
        headless = self._request.headless()
        info: dict[str, Any] = {
            "left_open": not headless,
            "mode": self._mode,
            "headless": headless,
            "history_recorded": not headless,
        }
        if headless:
            info["note"] = (
                "Disposable headless evidence only; Chrome was closed and no duplicate marker was written. "
                "Rerun headed for human review."
            )
        else:
            info["note"] = "Review the filled form in the open Chrome window; only a human may click publish."
        return info

    async def _disconnect(self) -> None:
        # connect_over_cdp: close() disconnects this client; the external Chrome stays alive.
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        if self._request.headless() and self._process is not None and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self._disconnect()
