# Fill-only contract

This project prepares a draft form; it is not an auto-publisher.

## Allowed actions

- Open the official Kuaishou Creator Center upload page.
- Attach the user-selected MP4 and cover.
- Fill and verify the combined title/description caption, up to three tags, and an explicitly requested future schedule.
- Save a local screenshot and JSON receipt.
- Leave the dedicated Chrome window open for human review in headed mode. Disposable headless runs close Chrome and do not write duplicate history.

Every browser click passes one shared allowlist. Click targets whose labels represent publishing or submission are denied. Platform adapters are statically checked for direct `.click()` calls and JavaScript click fallbacks.

## Excluded actions

There is no submit option, confirmation-dialog submission, submit retry, success readback, automatic login, account recovery, CAPTCHA handling, or verification-code entry. No other uploader is called as a fallback.

A future schedule only fills the platform's schedule controls. It does not authorize this program to publish immediately or at the scheduled time; the human remains responsible for the final action.

## Local data

- Chrome login state remains in the dedicated profile. Imported storage-state files are never printed or copied into evidence.
- Duplicate prevention uses only `kuaishou + SHA-256(video)` in `~/.fillup-skills/history/kuaishou.json` by default. It does not use titles, account identifiers, or remote databases.
- Screenshots and receipts default to `~/.fillup-skills/evidence/kuaishou/`. Screenshots can contain account or content details; review before sharing them.
- Set `--evidence-dir` and `--history-file` to controlled local paths for testing. Do not commit real profiles, storage states, media, evidence, or history.

## Honest result semantics

`ok:true,filled:true` means every listed field was filled and verified and the final screenshot was captured. `skipped:true` means the exact video was previously filled and no browser action occurred. Failures never create a duplicate marker. If form filling succeeded but the local duplicate marker could not be written, the result explicitly reports that condition and warns against rerunning.
