# Cloud Telegram reporting

One GitHub Actions workflow refreshes the RER C dashboard and sends the matching
report to a separate private chat with a Telegram bot.

## Setup

1. Open [@DmitriRERCScheduleBot2026_bot](https://t.me/DmitriRERCScheduleBot2026_bot) in Telegram and press **Start**.
2. Add the token from BotFather as the Actions secret `TELEGRAM_BOT_TOKEN`.
3. Add these Actions variables:
   - `TELEGRAM_CHAT_ID`: the chat ID for the new private chat with this bot.
   - `TELEGRAM_AUTOMATION_ENABLED`: `true`.

The repository already has the `IDFM_API_TOKEN` secret. The bot token only
controls this bot; it does not authorize access to your personal Telegram
account or other chats. Keep the token out of the repository and workflow logs.

## Schedule

`refresh-schedule.yml` runs every five minutes. Each run fetches fresh train
data from Île-de-France Mobilités and publishes changed `schedule.json` data for
the dashboard. It waits for the matching GitHub Pages deployment to succeed,
then sends a Telegram report from that same fetched schedule. Before sending, it
deletes the previous report and saves the new message ID in a short-lived
Actions artifact.

There is one five-minute update-and-send cycle. While open, `index.html`
reloads every five minutes and rereads `schedule.json` every thirty seconds.

The report appears in the bot's private chat, not in Saved Messages/«Я».
