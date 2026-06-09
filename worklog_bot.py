#!/usr/bin/env python3 -u
"""
Telegram bot interface for the personal worklog.

Run once as a background process:
  . ./secrets.env
  nohup venv/bin/python worklog_bot.py >> worklog_bot.log 2>&1 &

Commands:
  /add Title | Description | Category
  /start <id>
  /done <id>
  /list [todo|in-progress|done]
  /today
  /show <id>
  /help
"""

import os
import time
import requests
from worklog import (
    add_entry, start_entry, done_entry,
    list_entries, get_entry, fmt, init_db,
)

TG_TOKEN = os.environ["TG_BOT_TOKEN"]
CHAT_ID  = int(os.environ["TG_CHAT_ID"])
API      = f"https://api.telegram.org/bot{TG_TOKEN}"

HELP = (
    "Worklog commands:\n"
    "/add Title | Description | Category\n"
    "/start <id>\n"
    "/done <id>\n"
    "/list [todo|in-progress|done]\n"
    "/today\n"
    "/show <id>\n"
    "/help"
)


def send(text: str):
    requests.post(
        f"{API}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=15,
    )


def handle(text: str) -> str | None:
    text = text.strip()

    if text.startswith("/add"):
        parts = [p.strip() for p in text[4:].strip().split("|")]
        title = parts[0] if parts else ""
        if not title:
            return "Usage: /add Title | Description | Category"
        desc = parts[1] if len(parts) > 1 else ""
        cat  = parts[2] if len(parts) > 2 else ""
        eid  = add_entry(title, desc, cat)
        return f"Added #{eid}: {title}"

    if text.startswith("/start"):
        try:
            eid = int(text[6:].strip())
        except ValueError:
            return "Usage: /start <id>"
        start_entry(eid)
        row = get_entry(eid)
        return f"Started #{eid}: {row['title']}"

    if text.startswith("/done"):
        try:
            eid = int(text[5:].strip())
        except ValueError:
            return "Usage: /done <id>"
        dur = done_entry(eid)
        row = get_entry(eid)
        msg = f"Done #{eid}: {row['title']}"
        if dur is not None:
            msg += f" ({dur:.0f} min)"
        return msg

    if text.startswith("/list"):
        rest   = text[5:].strip()
        status = rest if rest in ("todo", "in-progress", "done") else None
        rows   = list_entries(status=status)
        return "\n".join(fmt(r, short=True) for r in rows) if rows else "No entries."

    if text.startswith("/today"):
        rows = list_entries(today=True)
        return "\n".join(fmt(r, short=True) for r in rows) if rows else "No entries today."

    if text.startswith("/show"):
        try:
            eid = int(text[5:].strip())
        except ValueError:
            return "Usage: /show <id>"
        row = get_entry(eid)
        return fmt(row) if row else f"Entry #{eid} not found."

    if text.startswith("/help"):
        return HELP

    return None


def poll():
    init_db()
    offset = None
    print("Worklog bot running — waiting for commands…")
    while True:
        try:
            params = {"timeout": 30, "allowed_updates": ["message"]}
            if offset:
                params["offset"] = offset
            resp    = requests.get(f"{API}/getUpdates", params=params, timeout=40)
            updates = resp.json().get("result", [])
            for u in updates:
                offset = u["update_id"] + 1
                msg    = u.get("message", {})
                if msg.get("chat", {}).get("id") != CHAT_ID:
                    continue
                body = msg.get("text", "")
                if body.startswith("/"):
                    reply = handle(body)
                    if reply:
                        send(reply)
        except Exception as e:
            print(f"[error] {e}")
            time.sleep(5)


if __name__ == "__main__":
    poll()
