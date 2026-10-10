"""SQLite persistence layer (standard library only)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    customer_id TEXT,
    channel TEXT,
    text TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    score REAL NOT NULL,
    themes TEXT NOT NULL,
    urgency INTEGER NOT NULL,
    keywords TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    theme TEXT,
    priority TEXT NOT NULL,
    rationale TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path = "data/insightflow.db"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def insert_feedback(self, record: dict[str, Any]) -> int:
        cur = self.conn.execute(
            """INSERT INTO feedback
               (source, customer_id, channel, text, sentiment, score, themes, urgency, keywords, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                record["source"], record.get("customer_id"), record.get("channel", "web"),
                record["text"], record["sentiment"], record["score"],
                json.dumps(record["themes"]), record["urgency"], json.dumps(record["keywords"]),
                record.get("created_at") or utcnow(),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_feedback(self, limit: int = 100, sentiment: str | None = None) -> list[dict]:
        sql = "SELECT * FROM feedback"
        args: list[Any] = []
        if sentiment:
            sql += " WHERE sentiment = ?"
            args.append(sentiment)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [self._row_to_feedback(r) for r in self.conn.execute(sql, args)]

    def all_feedback(self) -> list[dict]:
        return [self._row_to_feedback(r) for r in self.conn.execute("SELECT * FROM feedback ORDER BY id")]

    def insert_decision(self, d: dict[str, Any]) -> int:
        cur = self.conn.execute(
            "INSERT INTO decisions (title, theme, priority, rationale, status, created_at) VALUES (?,?,?,?,?,?)",
            (d["title"], d.get("theme"), d["priority"], d["rationale"], d.get("status", "open"), utcnow()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def list_decisions(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM decisions ORDER BY id DESC")]

    def update_decision_status(self, decision_id: int, status: str) -> bool:
        cur = self.conn.execute("UPDATE decisions SET status = ? WHERE id = ?", (status, decision_id))
        self.conn.commit()
        return cur.rowcount > 0

    def clear(self) -> None:
        self.conn.executescript("DELETE FROM feedback; DELETE FROM decisions;")

    @staticmethod
    def _row_to_feedback(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["themes"] = json.loads(d["themes"])
        d["keywords"] = json.loads(d["keywords"])
        return d
