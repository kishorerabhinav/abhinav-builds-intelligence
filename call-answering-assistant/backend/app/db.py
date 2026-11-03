"""SQLite storage for calls, assistant settings and device push tokens."""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

DEFAULT_SETTINGS: dict[str, str] = {
    "owner_name": "the person you're calling",
    "greeting": "",
    "instructions": "",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    sid TEXT PRIMARY KEY,
    from_number TEXT NOT NULL DEFAULT '',
    to_number TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress',
    transcript TEXT NOT NULL DEFAULT '[]',
    silent_turns INTEGER NOT NULL DEFAULT 0,
    caller_name TEXT,
    callback_number TEXT,
    reason TEXT,
    urgency TEXT,
    summary TEXT,
    is_read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS devices (token TEXT PRIMARY KEY, created_at TEXT NOT NULL);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._tx() as cur:
            cur.executescript(_SCHEMA)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    # ---- calls -------------------------------------------------------------

    def create_call(self, sid: str, from_number: str, to_number: str) -> None:
        with self._tx() as cur:
            cur.execute(
                "INSERT OR IGNORE INTO calls (sid, from_number, to_number, started_at) VALUES (?, ?, ?, ?)",
                (sid, from_number, to_number, now_iso()),
            )

    def get_call(self, sid: str) -> dict[str, Any] | None:
        with self._tx() as cur:
            row = cur.execute("SELECT * FROM calls WHERE sid = ?", (sid,)).fetchone()
        return _row_to_call(row) if row else None

    def list_calls(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._tx() as cur:
            rows = cur.execute(
                "SELECT * FROM calls ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_call(r) for r in rows]

    def append_turn(self, sid: str, role: str, text: str) -> list[dict[str, str]]:
        with self._tx() as cur:
            row = cur.execute("SELECT transcript FROM calls WHERE sid = ?", (sid,)).fetchone()
            transcript = json.loads(row["transcript"]) if row else []
            transcript.append({"role": role, "text": text})
            cur.execute(
                "UPDATE calls SET transcript = ?, silent_turns = 0 WHERE sid = ?",
                (json.dumps(transcript), sid),
            )
        return transcript

    def bump_silence(self, sid: str) -> int:
        with self._tx() as cur:
            cur.execute("UPDATE calls SET silent_turns = silent_turns + 1 WHERE sid = ?", (sid,))
            row = cur.execute("SELECT silent_turns FROM calls WHERE sid = ?", (sid,)).fetchone()
        return int(row["silent_turns"]) if row else 0

    def update_call(self, sid: str, **fields: Any) -> None:
        allowed = {
            "ended_at", "status", "caller_name", "callback_number",
            "reason", "urgency", "summary", "is_read",
        }
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return
        assignments = ", ".join(f"{k} = ?" for k in fields)
        with self._tx() as cur:
            cur.execute(f"UPDATE calls SET {assignments} WHERE sid = ?", (*fields.values(), sid))

    def delete_call(self, sid: str) -> bool:
        with self._tx() as cur:
            cur.execute("DELETE FROM calls WHERE sid = ?", (sid,))
            return cur.rowcount > 0

    # ---- settings ----------------------------------------------------------

    def get_settings(self) -> dict[str, str]:
        with self._tx() as cur:
            rows = cur.execute("SELECT key, value FROM settings").fetchall()
        return {**DEFAULT_SETTINGS, **{r["key"]: r["value"] for r in rows}}

    def save_settings(self, values: dict[str, str]) -> dict[str, str]:
        with self._tx() as cur:
            for key, value in values.items():
                if key in DEFAULT_SETTINGS:
                    cur.execute(
                        "INSERT INTO settings (key, value) VALUES (?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, value),
                    )
        return self.get_settings()

    # ---- devices -----------------------------------------------------------

    def add_device(self, token: str) -> None:
        with self._tx() as cur:
            cur.execute(
                "INSERT OR IGNORE INTO devices (token, created_at) VALUES (?, ?)", (token, now_iso())
            )

    def remove_device(self, token: str) -> None:
        with self._tx() as cur:
            cur.execute("DELETE FROM devices WHERE token = ?", (token,))

    def device_tokens(self) -> list[str]:
        with self._tx() as cur:
            return [r["token"] for r in cur.execute("SELECT token FROM devices").fetchall()]


def _row_to_call(row: sqlite3.Row) -> dict[str, Any]:
    call = dict(row)
    call["transcript"] = json.loads(call["transcript"])
    call["is_read"] = bool(call["is_read"])
    call.pop("silent_turns", None)
    return call
