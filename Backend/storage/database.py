from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: str | Path = "focus_guard.db") -> None:
        self.path = str(path)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY, started_at REAL NOT NULL, ended_at REAL,
                elapsed_seconds REAL NOT NULL, state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL,
                recorded_at REAL NOT NULL, score REAL NOT NULL, state TEXT NOT NULL,
                app_name TEXT, app_category TEXT, face_present INTEGER NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            """
        )
        self.connection.commit()

    def save_session(self, session: Any) -> None:
        self.connection.execute(
            """
            INSERT INTO sessions (id, started_at, ended_at, elapsed_seconds, state)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                started_at = excluded.started_at,
                ended_at = excluded.ended_at,
                elapsed_seconds = excluded.elapsed_seconds,
                state = excluded.state
            """,
            (session.id, session.started_at, session.ended_at, session.elapsed_seconds, session.state.value),
        )
        self.connection.commit()

    def save_telemetry(self, session_id: int, recorded_at: float, result: Any, face_present: bool) -> None:
        self.connection.execute(
            "INSERT INTO telemetry (session_id, recorded_at, score, state, app_name, app_category, face_present) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, recorded_at, result.score, result.state.value, result.app_name, result.app_category, int(face_present)),
        )
        self.connection.commit()

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def next_session_id(self) -> int:
        row = self.connection.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM sessions").fetchone()
        return int(row["next_id"])