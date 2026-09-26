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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
            );
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                email TEXT,
                created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
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

    def create_user(self, name: str, email: str, password: str) -> dict[str, Any]:
        existing = self.connection.execute(
            "SELECT * FROM users WHERE email = ? LIMIT 1",
            (email,),
        ).fetchone()
        if existing is not None:
            return self._redact_sensitive_values(dict(existing))

        cursor = self.connection.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password),
        )
        self.connection.commit()
        return self._redact_sensitive_values(
            {"id": cursor.lastrowid, "name": name, "email": email, "password": password}
        )

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM users ORDER BY id ASC").fetchall()
        return [self._redact_sensitive_values(dict(row)) for row in rows]

    def get_users(self) -> list[dict[str, Any]]:
        return self.list_users()

    def list_tables(self) -> list[dict[str, Any]]:
        tables = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [
            {
                "name": row["name"],
                "row_count": self.connection.execute(
                    f"SELECT COUNT(*) FROM {self._quote_identifier(row['name'])}"
                ).fetchone()[0],
            }
            for row in tables
        ]

    def inspect_table(self, table_name: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        table_names = {table["name"] for table in self.list_tables()}
        if table_name not in table_names:
            raise ValueError(f"Unknown table: {table_name}")

        quoted_name = self._quote_identifier(table_name)
        schema = self.connection.execute(f"PRAGMA table_info({quoted_name})").fetchall()
        columns = [
            {
                "name": column["name"],
                "type": column["type"],
                "not_null": bool(column["notnull"]),
                "primary_key": bool(column["pk"]),
            }
            for column in schema
        ]
        rows = self.connection.execute(
            f"SELECT * FROM {quoted_name} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        safe_rows = [
            {
                key: "[redacted]" if self._is_sensitive_column(key) else value
                for key, value in dict(row).items()
            }
            for row in rows
        ]
        total = self.connection.execute(f"SELECT COUNT(*) FROM {quoted_name}").fetchone()[0]
        return {"name": table_name, "columns": columns, "rows": safe_rows, "total": total}

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    @staticmethod
    def _is_sensitive_column(column_name: str) -> bool:
        lowered = column_name.lower()
        return any(marker in lowered for marker in ("password", "secret", "token"))

    @classmethod
    def _redact_sensitive_values(cls, values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: "[redacted]" if cls._is_sensitive_column(key) else value
            for key, value in values.items()
        }

    def create_admin(self, username: str, password: str, email: str | None = None) -> dict[str, Any]:
        existing = self.connection.execute(
            "SELECT * FROM admins WHERE username = ? LIMIT 1",
            (username,),
        ).fetchone()
        if existing is not None:
            return self._redact_sensitive_values(dict(existing))

        cursor = self.connection.execute(
            "INSERT INTO admins (username, password, email) VALUES (?, ?, ?)",
            (username, password, email),
        )
        self.connection.commit()
        return self._redact_sensitive_values(
            {"id": cursor.lastrowid, "username": username, "password": password, "email": email}
        )

    def list_admins(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM admins ORDER BY id ASC").fetchall()
        return [self._redact_sensitive_values(dict(row)) for row in rows]

    def verify_admin(self, username: str, password: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM admins WHERE username = ? AND password = ? LIMIT 1",
            (username, password),
        ).fetchone()
        return row is not None

    def validate_admin(self, username: str, password: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM admins WHERE username = ? AND password = ? LIMIT 1",
            (username, password),
        ).fetchone()
        return self._redact_sensitive_values(dict(row)) if row else None

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def next_session_id(self) -> int:
        row = self.connection.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM sessions").fetchone()
        return int(row["next_id"])