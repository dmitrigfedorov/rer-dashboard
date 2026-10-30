# Cloud Telegram reporting

The RER schedule updater runs on GitHub Actions and can send the latest
`schedule.json` to a separate private chat with a Telegram bot.

## Setup

1. Open [@DmitriRERCScheduleBot2026_bot](https://t.me/DmitriRERCScheduleBot2026_bot) in Telegram and press **Start**.
2. Add the token from BotFather as the Actions secret `TELEGRAM_BOT_TOKEN`.
3. Add these Actions variables:
   - `TELEGRAM_CHAT_ID`: the chat ID for the new private chat with this bot.
   - `TELEGRAM_AUTOMATION_ENABLED`: `true`.

The repository already has the `IDFM_API_TOKEN` secret. The bot token only
controls this bot; it does not authorize access to your personal Telegram
account or other chats. Keep the token out of the repository and workflow logs.

The workflow runs on GitHub-hosted runners every five minutes. It saves only
the previous bot message ID in a short-lived Actions artifact, deletes that
message, and then sends the current report. The report appears in the new bot
chat, not in Saved Messages/«Я».
