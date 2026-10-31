# Cloudflare Cron dispatcher

This Worker dispatches the existing GitHub Actions workflow every five minutes. It runs outside the local computer; the workflow refreshes the dashboard and sends the report to the existing Telegram bot conversation.

## Configuration

The Worker targets `dmitrigfedorov/rer-dashboard`, branch `main`, workflow `.github/workflows/refresh-schedule.yml`. Only the GitHub credential is configured as a secret.

Add `GITHUB_TOKEN` as an encrypted Production Worker secret. Use a fine-grained GitHub token restricted to this repository with **Metadata: Read-only** and **Actions: Read and write**. Never put the token in this repository.

Cloudflare builds this Worker from this directory. The Wrangler config installs the `*/5 * * * *` Cron Trigger. After confirming that Cloudflare dispatches successfully, remove the `schedule` trigger from the GitHub workflow and keep `workflow_dispatch` for manual runs.

The workflow's concurrency group serializes overlapping runs. Cloudflare Worker logs show dispatch errors; GitHub Actions logs show refresh, publish, and Telegram delivery results.
