# Cloudflare Cron dispatcher

This Worker dispatches the existing GitHub Actions workflow every five minutes. The Worker runs outside the local computer; the workflow continues to refresh the dashboard and send the report to the existing Telegram bot conversation.

## Deploy

From this directory, deploy with Wrangler or create a Worker in the Cloudflare dashboard using `worker.js` as its entry point and `*/5 * * * *` as its Cron Trigger.

Configure these Worker variables:

- `GITHUB_OWNER`: `dmitrigfedorov`
- `GITHUB_REPO`: `rer-dashboard`
- `GITHUB_REF`: `main`

Add `GITHUB_TOKEN` as an encrypted Worker secret. Use a fine-grained GitHub token restricted to this repository with **Actions: Read and write** permission. Never put the token in this repository.

After deployment, use the Worker’s **Run** action or wait for a Cron Trigger, then confirm a new run appears under GitHub Actions. Only after confirming the Cloudflare dispatch works, remove the `schedule` trigger from `.github/workflows/refresh-schedule.yml`; keep `workflow_dispatch` for manual runs. Leaving both schedulers enabled would create duplicate runs.

The workflow’s concurrency group serializes overlapping runs. Cloudflare Worker logs show dispatch errors; GitHub Actions logs show refresh, publish, and Telegram delivery results.
