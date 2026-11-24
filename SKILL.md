---
name: kuaishou-fill
description: Fill a video, cover, title, description, up to three tags, and optional schedule into Kuaishou Creator Center in a dedicated logged-in Chrome, then stop before publishing. Use whenever the user asks to upload, prepare, fill, or schedule a Kuaishou video without directly publishing it. This skill never clicks publish, never automates login, and never handles verification challenges.
license: MIT
version: 1.0.0
---

# Kuaishou fill-only

Use this skill to prepare one Kuaishou video post for human review. The terminal state is a **filled form in an open dedicated Chrome window**, not a published post. Kuaishou has one caption editor, so the CLI writes the title and description into that caption rather than inventing a separate title field.

## Hard boundary

- Always pass `--fill-only`; there is deliberately no submit option.
- Do not click or script around 发布, 立即发布, 确认发布, 提交, or their equivalents, including with another browser tool.
- Do not log in, refresh accounts, solve CAPTCHAs, or enter verification codes. Ask the user to do those manually in the dedicated Chrome profile.
- Use only media and account profiles the user supplied or approved. Do not invent titles, schedules, paths, or account details.
- Do not claim success from a screenshot alone. The CLI must return `ok:true` and list the fields it verified.

## Prepare

1. Resolve this skill's directory; all commands below run from that directory.
2. Confirm an absolute faststart MP4 path and a JPG/PNG/WebP cover path.
3. Confirm the title and description. Supply at most three tags; use `--schedule` only when the user explicitly requests scheduling.
4. Prefer the default headed Chrome. Headless mode is disposable evidence only: Chrome is closed, no duplicate marker is written, and a headed rerun is required for human review.
5. Install the exact dependency when missing:

   ```bash
   python3 -m pip install -r requirements.txt
   python3 -m playwright install chromium
   ```

6. The user must already be logged into Kuaishou Creator Center in a dedicated Chrome profile. Never use their everyday Default profile. A Playwright `--storage-state` JSON may be supplied instead; treat it as a credential and never print its contents.

## Fill

```bash
python3 scripts/kuaishou_fill.py \
  --video /absolute/video.mp4 \
  --cover /absolute/cover.jpg \
  --title "User-approved title" \
  --desc "User-approved description" \
  --tags "tag1,tag2" \
  --chrome-profile /absolute/dedicated-chrome-profile \
  --fill-only
```

Add `--schedule "YYYY-MM-DD HH:MM"` only for an explicit future local schedule. To attach to an existing dedicated Chrome started with remote debugging, add `--cdp-url http://127.0.0.1:PORT`; remote CDP hosts are rejected.

The script writes one JSON object to stdout. Progress and errors go to stderr. Exit code 0 means filled or intentionally skipped; other codes mean not completed.

```json
{"contract_version":1,"platform":"kuaishou","ok":true,"filled":true,"skipped":false,"submit":"left_to_human","evidence":{"fields":["video","title","description","tags","cover"],"screenshot":"/private/local/filled.png"},"browser":{"left_open":true,"mode":"dedicated_profile","headless":false,"note":"Review the filled form in the open Chrome window; only a human may click publish."}}
```

If the same video SHA-256 was already filled on Kuaishou, the CLI returns `skipped:true`, `reason:"already_filled"` and performs no browser action. Do not delete the user's local history to force a repeat; explain the skip and ask how they want to proceed.

## Handoff and failures

1. Show the JSON result and evidence screenshot to the user.
2. When `ok:true,filled:true`, tell them to review the open Chrome window. Only the human decides whether to publish.
3. For `logged_out`, ask the user to sign in manually in the dedicated profile and rerun.
4. For `manual_intervention_required`, stop and let the user complete verification.
5. For `video_not_faststart`, suggest remuxing to a new file with `ffmpeg -i input.mp4 -c copy -movflags +faststart output.mp4`; never overwrite the source.
6. For selector or cover failures, preserve the browser and evidence. Do not fall back to arbitrary clicking or another uploader that can submit.

See `docs/fill-only.md` for the safety contract and data-handling rules.
