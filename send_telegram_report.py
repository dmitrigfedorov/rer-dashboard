"""Send the refreshed RER schedule to the user's Telegram chat."""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from typing import Any

import requests

ARTIFACT_NAME = "rer-message-state"
API_ROOT = "https://api.github.com"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required GitHub Actions secret or variable: {name}")
    return value


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def previous_message_id(token: str) -> int | None:
    repo = required("GITHUB_REPOSITORY")
    this_run = int(required("GITHUB_RUN_ID"))
    workflow = os.environ.get("GITHUB_WORKFLOW_FILE", "update-schedule.yml")
    api_headers = headers(token)
    response = requests.get(
        f"{API_ROOT}/repos/{repo}/actions/workflows/{workflow}/runs",
        params={"branch": os.environ.get("GITHUB_REF_NAME", "main"), "per_page": 20},
        headers=api_headers,
        timeout=20,
    )
    response.raise_for_status()

    for run in response.json().get("workflow_runs", []):
        if int(run["id"]) == this_run or run.get("status") != "completed":
            continue
        artifact_response = requests.get(
            f"{API_ROOT}/repos/{repo}/actions/runs/{run['id']}/artifacts",
            params={"per_page": 100},
            headers=api_headers,
            timeout=20,
        )
        artifact_response.raise_for_status()
        artifact = next(
            (
                item
                for item in artifact_response.json().get("artifacts", [])
                if item.get("name") == ARTIFACT_NAME and not item.get("expired")
            ),
            None,
        )
        if artifact is None:
            continue
        archive = requests.get(
            f"{API_ROOT}/repos/{repo}/actions/artifacts/{artifact['id']}/zip",
            headers=api_headers,
            timeout=30,
        )
        archive.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(archive.content)) as zipped:
            with zipped.open("message_state.json") as state_file:
                return int(json.load(state_file)["message_id"])
    return None


def format_report(schedule: dict[str, Any]) -> str:
    fetched_at = str(schedule.get("fetchedAtParis", "")).replace(", ", " ")
    lines = [f"🚆 RER C — обновлено {fetched_at}".rstrip()]
    for direction in schedule.get("directions", []):
        title = f"{direction.get('title', '')} → {direction.get('destination', '')}".strip(" →")
        lines.extend(("", title))
        rows = direction.get("rows") or []
        if not rows:
            lines.append("Нет ближайших отправлений")
            continue
        for row in rows:
            details = [str(row.get("train", "")), str(row.get("destinationName", ""))]
            if row.get("platform"):
                details.append(f"voie {row['platform']}")
            if row.get("status"):
                details.append(str(row["status"]))
            lines.append(f"{row.get('from', '')}–{row.get('to', '')} · " + " · ".join(x for x in details if x))
    return "\n".join(lines)


def bot_api(method: str, values: dict[str, Any]) -> dict[str, Any]:
    token = required("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        response = requests.post(url, json=values, timeout=20)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        # Do not include the request URL: it contains the bot token.
        raise RuntimeError("Telegram Bot API request failed") from None
    if not result.get("ok"):
        raise RuntimeError("Telegram Bot API rejected the request")
    return result["result"]


def send(report: str, chat_id: int, old_message_id: int | None) -> int:
    if old_message_id is not None:
        bot_api("deleteMessage", {"chat_id": chat_id, "message_id": old_message_id})
    sent = bot_api("sendMessage", {"chat_id": chat_id, "text": report})
    return int(sent["message_id"])


def main() -> None:
    with Path("schedule.json").open(encoding="utf-8") as source:
        schedule = json.load(source)
    report = format_report(schedule)
    github_token = required("GITHUB_TOKEN")
    old_id = previous_message_id(github_token)
    message_id = send(report, int(required("TELEGRAM_CHAT_ID")), old_id)
    with Path("message_state.json").open("w", encoding="utf-8") as state_file:
        json.dump({"message_id": message_id}, state_file)
    print("RER report sent; prior report removed when one was available.")


if __name__ == "__main__":
    main()
