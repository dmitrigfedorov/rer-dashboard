# Cloud Telegram reporting

The Telegram report and dashboard data refresh run as separate GitHub Actions workflows.

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

- `refresh-schedule.yml` runs every five minutes. It sends the latest published
  `schedule.json` to the bot chat, deletes the previous report, and stores the
  new message ID in a short-lived Actions artifact.
- `update-schedule.yml` runs every fifteen minutes. It fetches fresh data from
  Île-de-France Mobilités and publishes changed schedule data for the dashboard.
  It does not send Telegram messages.
- `index.html` reloads every five minutes and refreshes `schedule.json` every
  thirty seconds while open.

The report appears in the bot's private chat, not in Saved Messages/«Я».
