# kuaishou-fill

English | [简体中文](./README.zh-CN.md)

An independently installable agent skill that fills a Kuaishou Creator Center video form and **stops before publishing**. It gives Claude Code, Codex, OpenClaw, ZCode, and other agents one deterministic CLI instead of asking them to improvise browser clicks.

Sister project: [douyin-fill](https://github.com/huiguyy/douyin-fill). The form-flow design acknowledges [social-auto-upload](https://github.com/dreammis/social-auto-upload); human pacing acknowledges [Easel](https://github.com/ZJU-REAL/Easel). See `NOTICE`.

## Why fill-only

The agent attaches the video and cover, fills the requested metadata, captures evidence, and leaves the dedicated Chrome window open. A human reviews the actual form and decides whether to publish. There is no submit flag, hidden submission path, publish retry, login automation, or CAPTCHA handling.

Kuaishou exposes one caption editor, so the title and description are filled together rather than pretending a separate title field exists.

## Install

Requires Python 3.10+, Chrome/Chromium, and a separate Chrome profile already logged into Kuaishou Creator Center.

```bash
npx skills add huiguyy/kuaishou-fill
```

Or clone this repository and copy/symlink its directory as `~/.agents/skills/kuaishou-fill` (or your agent's equivalent skills directory). From the installed skill directory:

```bash
python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
```

The runtime dependency is exactly pinned. The CLI `--help` command works without Playwright installed, so agents can inspect the contract safely.

## Use

```bash
python3 scripts/kuaishou_fill.py \
  --video /absolute/video.mp4 \
  --cover /absolute/cover.jpg \
  --title "A reviewed title" \
  --desc "A reviewed description" \
  --tags "one,two" \
  --chrome-profile /absolute/dedicated-chrome-profile \
  --fill-only
```

Optional inputs:

- `--storage-state /private/storage-state.json`: import existing Playwright login state without printing it.
- `--cdp-url http://127.0.0.1:PORT`: attach to an existing dedicated Chrome; only loopback URLs are accepted.
- `--schedule "YYYY-MM-DD HH:MM"`: fill a future local schedule only when explicitly requested.
- `--headless`: capture disposable evidence, close Chrome, and skip duplicate history; a headed rerun is required for human review.
- `--chrome-path`, `--evidence-dir`, `--history-file`, `--timeout`: controlled runtime overrides.

The video must be a faststart MP4 (`moov` before the first `mdat`). Validation happens before Chrome opens and never rewrites the source file. At most three tags are accepted.

## Result

Stdout is exactly one JSON object; logs go to stderr. A successful result contains `ok:true`, `filled:true`, verified `evidence.fields`, a local screenshot, and `submit:"left_to_human"`. Headed runs report `browser.left_open:true`; disposable headless runs report `left_open:false` and `history_recorded:false`.

Repeating the same video on Kuaishou returns `skipped:true, reason:"already_filled"` without opening Chrome. This is an intentionally small local guard based only on platform and video SHA-256.

See [the fill-only contract](docs/fill-only.md) for security, privacy, error, and evidence semantics.

## Verify

```bash
sh tools/run_checks.sh
python3 -m unittest discover -s tests -v
```

Checks include compilation, isolated CLI help, media atom parsing, duplicate behavior, input/output contracts, exact dependency pins, redline scanning, vendored-core consistency where applicable, and mutation tests proving the fill-only gate fails on an unsafe implementation. Real platform availability and selector compatibility still require a separately authorized test account; no publish action is part of verification.

## License

MIT for this project. Third-party notices and the SAU MIT / Easel Apache-2.0 texts are included under `licenses/`. This project is not affiliated with Kuaishou.
