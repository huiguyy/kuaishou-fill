"""Identical command-line surface for both independently packaged skills."""
from __future__ import annotations

import argparse
from typing import Any, Callable

from .contract import CONTRACT_VERSION, FillRequest, FillResult
from .errors import FillError
from .runner import Adapter, run_fill


class JsonArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, platform: str, **kwargs: Any) -> None:
        self._platform = platform
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> None:
        raise FillError("invalid_arguments", message, exit_code=2)


def build_parser(platform: str, script_name: str) -> JsonArgumentParser:
    parser = JsonArgumentParser(
        prog=script_name,
        platform=platform,
        description=f"Fill the {platform} video form and stop before publishing. No submit option exists.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--video", required=True, help="Local faststart MP4 path")
    parser.add_argument("--cover", required=True, help="Local JPG, PNG, or WebP cover path")
    parser.add_argument("--title", required=True, help="Post title")
    parser.add_argument("--desc", default="", help="Post description")
    parser.add_argument("--tags", default="", help="Comma-separated tags, with or without #")
    parser.add_argument("--storage-state", help="Playwright storage_state JSON (sensitive)")
    parser.add_argument("--chrome-profile", help="Dedicated Chrome user-data directory")
    parser.add_argument("--headless", action="store_true", help="Disposable evidence only; close Chrome and skip duplicate history")
    parser.add_argument("--schedule", help="Local schedule time: YYYY-MM-DD HH:MM")
    parser.add_argument("--fill-only", required=True, action="store_true", help="Required safety acknowledgement; never submits")
    parser.add_argument("--chrome-path", help="Explicit Chrome/Chromium executable")
    parser.add_argument("--cdp-url", help="Attach to an existing loopback Chrome debugging URL")
    parser.add_argument("--evidence-dir", help="Evidence parent directory (default: user data directory)")
    parser.add_argument("--history-file", help="Local single-file duplicate history path")
    parser.add_argument("--timeout", type=int, default=480, help="Upload wait timeout in seconds (30-3600)")
    parser.add_argument("--version", action="version", version=f"%(prog)s contract-v{CONTRACT_VERSION}")
    return parser


def main(platform: str, script_name: str, adapter: Adapter) -> int:
    parser = build_parser(platform, script_name)
    try:
        args = parser.parse_args()
        request = (
            FillRequest.builder(platform)
            .with_media(args.video, args.cover)
            .with_metadata(args.title, args.desc, args.tags)
            .with_authentication(storage_state=args.storage_state, chrome_profile=args.chrome_profile)
            .with_browser(headless=args.headless, chrome_path=args.chrome_path, cdp_url=args.cdp_url)
            .with_schedule(args.schedule)
            .with_paths(evidence_root=args.evidence_dir, history_file=args.history_file)
            .with_timeout(args.timeout)
            .with_fill_only(args.fill_only)
            .build()
        )
    except FillError as exc:
        print(FillResult.failure(platform, exc).to_json(), flush=True)
        return exc.exit_code
    result, exit_code = run_fill(request, adapter)
    print(result.to_json(), flush=True)
    return exit_code
