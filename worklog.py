#!/usr/bin/env python3
"""Personal task/activity worklog — SQLite backend + CLI."""

import os
import sqlite3
import argparse
from datetime import datetime

DB_PATH = os.path.expanduser("~/yt-agent/worklog.db")

STATUS_ICON = {"todo": "○", "in-progress": "◑", "done": "●"}


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                description  TEXT    DEFAULT '',
                category     TEXT    DEFAULT '',
                status       TEXT    DEFAULT 'todo',
                started_at   TEXT,
                ended_at     TEXT,
                duration_min REAL,
                created_at   TEXT    DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
            )
        """)


def add_entry(title: str, description: str = "", category: str = "") -> int:
    init_db()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO entries (title, description, category) VALUES (?, ?, ?)",
            (title, description, category),
        )
        return cur.lastrowid


def start_entry(entry_id: int):
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with _conn() as conn:
        conn.execute(
            "UPDATE entries SET status='in-progress', started_at=? WHERE id=?",
            (now, entry_id),
        )


def done_entry(entry_id: int) -> float | None:
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with _conn() as conn:
        row = conn.execute("SELECT started_at FROM entries WHERE id=?", (entry_id,)).fetchone()
        duration = None
        if row and row["started_at"]:
            delta = datetime.fromisoformat(now) - datetime.fromisoformat(row["started_at"])
            duration = delta.total_seconds() / 60
        conn.execute(
            "UPDATE entries SET status='done', ended_at=?, duration_min=? WHERE id=?",
            (now, duration, entry_id),
        )
        return duration


def list_entries(status: str = None, category: str = None, today: bool = False):
    init_db()
    sql = "SELECT * FROM entries WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"
        params.append(status)
    if category:
        sql += " AND category=?"
        params.append(category)
    if today:
        sql += " AND date(created_at)=date('now','localtime')"
    sql += " ORDER BY created_at DESC"
    with _conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_entry(entry_id: int):
    init_db()
    with _conn() as conn:
        return conn.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()


def fmt(row, short: bool = False) -> str:
    icon = STATUS_ICON.get(row["status"], "?")
    cat  = f"[{row['category']}] " if row["category"] else ""
    dur  = f" ({row['duration_min']:.0f}min)" if row["duration_min"] else ""
    line = f"{icon} #{row['id']} {cat}{row['title']}{dur}"
    if short:
        return line
    parts = [line]
    if row["description"]:
        parts.append(f"   {row['description']}")
    if row["started_at"]:
        parts.append(f"   started : {row['started_at']}")
    if row["ended_at"]:
        parts.append(f"   ended   : {row['ended_at']}")
    parts.append(    f"   created : {row['created_at']}")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(prog="worklog", description="Personal worklog")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("add", help="Add a new entry")
    p.add_argument("title")
    p.add_argument("-d", "--desc",     default="", help="Description")
    p.add_argument("-c", "--category", default="", help="Category / project tag")

    p = sub.add_parser("start", help="Mark as in-progress (records start time)")
    p.add_argument("id", type=int)

    p = sub.add_parser("done", help="Mark as done (records end time + duration)")
    p.add_argument("id", type=int)

    p = sub.add_parser("list", help="List entries")
    p.add_argument("--status",   choices=["todo", "in-progress", "done"])
    p.add_argument("--category", "-c")
    p.add_argument("--today",    action="store_true", help="Only today's entries")

    p = sub.add_parser("today", help="List today's entries")

    p = sub.add_parser("show", help="Show full details of an entry")
    p.add_argument("id", type=int)

    args = parser.parse_args()

    if args.cmd == "add":
        eid = add_entry(args.title, args.desc, args.category)
        print(f"Added #{eid}: {args.title}")

    elif args.cmd == "start":
        start_entry(args.id)
        row = get_entry(args.id)
        print(f"Started #{args.id}: {row['title']}")

    elif args.cmd == "done":
        dur = done_entry(args.id)
        row = get_entry(args.id)
        msg = f"Done #{args.id}: {row['title']}"
        if dur is not None:
            msg += f"  ({dur:.0f} min)"
        print(msg)

    elif args.cmd == "list":
        rows = list_entries(args.status, args.category, args.today)
        if not rows:
            print("No entries.")
            return
        for r in rows:
            print(fmt(r, short=True))

    elif args.cmd == "today":
        rows = list_entries(today=True)
        if not rows:
            print("No entries today.")
            return
        for r in rows:
            print(fmt(r, short=True))

    elif args.cmd == "show":
        row = get_entry(args.id)
        print(fmt(row) if row else f"Entry #{args.id} not found.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
