"""Session store backends for persistent and in-memory session management."""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class SessionStore(Protocol):
    """Minimal protocol for session persistence backends."""

    def create(self, session_id: str, ip_address: str, user_id: str = "") -> dict[str, Any]: ...

    def get(self, session_id: str) -> dict[str, Any] | None: ...

    def touch(self, session_id: str) -> None: ...

    def delete(self, session_id: str) -> None: ...

    def count_active(self) -> int: ...

    def cleanup_expired(self, idle_timeout: int, absolute_timeout: int) -> int: ...


class MemorySessionStore:
    """In-memory session store.  Sessions are lost on process restart."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def create(self, session_id: str, ip_address: str, user_id: str = "") -> dict[str, Any]:
        now = time.time()
        session = {
            "id": session_id,
            "user_id": user_id,
            "ip_address": ip_address,
            "created_at": now,
            "last_activity_at": now,
        }
        self._sessions[session_id] = session
        return dict(session)

    def get(self, session_id: str) -> dict[str, Any] | None:
        session = self._sessions.get(session_id)
        return dict(session) if session else None

    def touch(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session["last_activity_at"] = time.time()

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def count_active(self) -> int:
        return len(self._sessions)

    def cleanup_expired(self, idle_timeout: int, absolute_timeout: int) -> int:
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if (now - s["last_activity_at"] > idle_timeout) or (now - s["created_at"] > absolute_timeout)
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)


class SQLiteSessionStore:
    """SQLite-backed session store.  Sessions persist across restarts."""

    _TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL DEFAULT '',
        ip_address TEXT NOT NULL DEFAULT '',
        created_at REAL NOT NULL,
        last_activity_at REAL NOT NULL
    )
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(self._TABLE_SQL)
            self._conn.commit()
        return self._conn

    def _ensure_table(self) -> None:
        conn = self._get_conn()
        conn.execute(self._TABLE_SQL)
        conn.commit()

    def create(self, session_id: str, ip_address: str, user_id: str = "") -> dict[str, Any]:
        now = time.time()
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO sessions (id, user_id, ip_address, created_at, last_activity_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, ip_address, now, now),
        )
        conn.commit()
        return {
            "id": session_id,
            "user_id": user_id,
            "ip_address": ip_address,
            "created_at": now,
            "last_activity_at": now,
        }

    def get(self, session_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def touch(self, session_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET last_activity_at = ? WHERE id = ?",
            (time.time(), session_id),
        )
        conn.commit()

    def delete(self, session_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()

    def count_active(self) -> int:
        conn = self._get_conn()
        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row[0] if row else 0

    def cleanup_expired(self, idle_timeout: int, absolute_timeout: int) -> int:
        now = time.time()
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM sessions WHERE (? - last_activity_at > ?) OR (? - created_at > ?)",
            (now, idle_timeout, now, absolute_timeout),
        )
        conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def create_session_store(store_type: str, data_dir: str = "") -> MemorySessionStore | SQLiteSessionStore:
    """Factory: create a session store from config."""
    if store_type == "sqlite" and data_dir:
        from pathlib import Path

        db_path = str(Path(data_dir) / "sessions.db")
        return SQLiteSessionStore(db_path)
    return MemorySessionStore()
