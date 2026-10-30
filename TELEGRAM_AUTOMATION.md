# Cloud Telegram reporting

The RER schedule updater runs on GitHub Actions. This optional step sends its
latest `schedule.json` to the personal Telegram chat configured by the owner.

## Required Actions secrets

The repository already uses `IDFM_API_TOKEN` for the RER schedule updater.
For Telegram, add these Actions secrets:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_SESSION` (Telethon StringSession for the signed-in personal account)
- `TELEGRAM_CHAT_ID`

Then add the Actions variable `TELEGRAM_AUTOMATION_ENABLED=true` to enable
sending. Leave it unset to keep the Telegram step disabled.

A Telethon StringSession is a full Telegram account authorization, not a
send-only credential. Store it only as a GitHub Actions secret and never in
the repository, workflow logs, or issue/PR text. The public repository stores
only workflow code; the report message ID is retained briefly in a GitHub
Actions artifact so the next run can delete the previous report before sending.

The workflow uses the GitHub Actions schedule already used by this repository.
Scheduled jobs run on GitHub-hosted runners; GitHub may delay scheduled starts
during periods of high load.
