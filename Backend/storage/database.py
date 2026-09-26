from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
from pathlib import Path
from time import time
from typing import Any


class Database:
    _PASSWORD_ITERATIONS = 310_000

    def __init__(self, path: str | Path = "focus_guard.db") -> None:
        requested_path = Path(path)
        if requested_path == Path("focus_guard.db"):
            requested_path = Path(__file__).resolve().parents[2] / "focus_guard.db"
        self.path = str(requested_path)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
                started_at REAL NOT NULL, ended_at REAL,
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
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
            );
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                email TEXT,
                created_at REAL NOT NULL DEFAULT (strftime('%s', 'now'))
            );
            CREATE TABLE IF NOT EXISTS user_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at REAL NOT NULL
            );
            """
        )
        session_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(sessions)")
        }
        if "user_id" not in session_columns:
            self.connection.execute(
                "ALTER TABLE sessions ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )
        user_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(users)")
        }
        if "must_change_password" not in user_columns:
            self.connection.execute(
                "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"
            )
        self.connection.commit()

    def save_session(self, session: Any, user_id: int | None = None) -> None:
        self.connection.execute(
            """
            INSERT INTO sessions (id, user_id, started_at, ended_at, elapsed_seconds, state)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                user_id = COALESCE(excluded.user_id, sessions.user_id),
                started_at = excluded.started_at,
                ended_at = excluded.ended_at,
                elapsed_seconds = excluded.elapsed_seconds,
                state = excluded.state
            """,
            (session.id, user_id, session.started_at, session.ended_at, session.elapsed_seconds, session.state.value),
        )
        self.connection.commit()

    def save_telemetry(self, session_id: int, recorded_at: float, result: Any, face_present: bool) -> None:
        self.connection.execute(
            "INSERT INTO telemetry (session_id, recorded_at, score, state, app_name, app_category, face_present) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, recorded_at, result.score, result.state.value, result.app_name, result.app_category, int(face_present)),
        )
        self.connection.commit()

    def create_user(self, name: str, email: str, password: str) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        try:
            cursor = self.connection.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name.strip(), normalized_email, self._hash_password(password)),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError("An account with this email already exists") from error
        self.connection.commit()
        return {
            "id": cursor.lastrowid,
            "name": name.strip(),
            "email": normalized_email,
            "must_change_password": False,
        }

    def verify_user(self, email: str, password: str) -> dict[str, Any] | None:
        normalized_email = email.strip().lower()
        row = self.connection.execute(
            "SELECT id, name, email, password, must_change_password FROM users WHERE email = ? LIMIT 1",
            (normalized_email,),
        ).fetchone()
        if row is None or not self._verify_password(password, row["password"]):
            return None

        if not row["password"].startswith("pbkdf2_sha256$"):
            self.connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (self._hash_password(password), row["id"]),
            )
            self.connection.commit()
        return {
            "id": row["id"],
            "name": row["name"],
            "email": row["email"],
            "must_change_password": bool(row["must_change_password"]),
        }

    def reset_user_password(self, user_id: int) -> str | None:
        temporary_password = secrets.token_urlsafe(12)
        cursor = self.connection.execute(
            "UPDATE users SET password = ?, must_change_password = 1 WHERE id = ?",
            (self._hash_password(temporary_password), user_id),
        )
        if cursor.rowcount == 0:
            self.connection.rollback()
            return None
        self.connection.execute("DELETE FROM user_tokens WHERE user_id = ?", (user_id,))
        self.connection.commit()
        return temporary_password

    def change_user_password(self, user_id: int, new_password: str) -> dict[str, Any] | None:
        cursor = self.connection.execute(
            "UPDATE users SET password = ?, must_change_password = 0 WHERE id = ?",
            (self._hash_password(new_password), user_id),
        )
        if cursor.rowcount == 0:
            self.connection.rollback()
            return None
        self.connection.execute("DELETE FROM user_tokens WHERE user_id = ?", (user_id,))
        row = self.connection.execute(
            "SELECT id, name, email, must_change_password FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        self.connection.commit()
        if row is None:
            return None
        return dict(row) | {"must_change_password": bool(row["must_change_password"])}

    def delete_user(self, user_id: int) -> bool:
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            exists = self.connection.execute(
                "SELECT 1 FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if exists is None:
                self.connection.rollback()
                return False
            self.connection.execute(
                "DELETE FROM telemetry WHERE session_id IN "
                "(SELECT id FROM sessions WHERE user_id = ?)",
                (user_id,),
            )
            self.connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            self.connection.execute("DELETE FROM user_tokens WHERE user_id = ?", (user_id,))
            self.connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.connection.commit()
            return True
        except Exception:
            self.connection.rollback()
            raise

    def issue_user_token(self, user_id: int, lifetime_seconds: int = 86_400) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.connection.execute(
            "INSERT INTO user_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (token_hash, user_id, time() + lifetime_seconds),
        )
        self.connection.commit()
        return token

    def get_user_for_token(self, token: str) -> dict[str, Any] | None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = self.connection.execute(
            """
            SELECT users.id, users.name, users.email, users.must_change_password
            FROM user_tokens
            JOIN users ON users.id = user_tokens.user_id
            WHERE user_tokens.token_hash = ? AND user_tokens.expires_at > ?
            """,
            (token_hash, time()),
        ).fetchone()
        if row is None:
            return None
        return dict(row) | {"must_change_password": bool(row["must_change_password"])}

    def revoke_user_token(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.connection.execute("DELETE FROM user_tokens WHERE token_hash = ?", (token_hash,))
        self.connection.commit()

    @classmethod
    def _hash_password(cls, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, cls._PASSWORD_ITERATIONS)
        return "pbkdf2_sha256${}${}${}".format(
            cls._PASSWORD_ITERATIONS,
            base64.b64encode(salt).decode(),
            base64.b64encode(digest).decode(),
        )

    @staticmethod
    def _verify_password(password: str, encoded: str | None) -> bool:
        if not isinstance(encoded, str):
            return False
        if not encoded.startswith("pbkdf2_sha256$"):
            return hmac.compare_digest(password, encoded)
        try:
            algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            salt = base64.b64decode(salt_text, validate=True)
            expected = base64.b64decode(digest_text, validate=True)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

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
            (username, self._hash_password(password), email),
        )
        self.connection.commit()
        return self._redact_sensitive_values(
            {"id": cursor.lastrowid, "username": username, "email": email}
        )

    def list_admins(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM admins ORDER BY id ASC").fetchall()
        return [self._redact_sensitive_values(dict(row)) for row in rows]

    def verify_admin(self, username: str, password: str) -> bool:
        row = self.connection.execute(
            "SELECT id, password FROM admins WHERE username = ? LIMIT 1",
            (username,),
        ).fetchone()
        if row is None or not self._verify_password(password, row["password"]):
            return False
        if not row["password"].startswith("pbkdf2_sha256$"):
            self.connection.execute(
                "UPDATE admins SET password = ? WHERE id = ?",
                (self._hash_password(password), row["id"]),
            )
            self.connection.commit()
        return True

    def validate_admin(self, username: str, password: str) -> dict[str, Any] | None:
        if not self.verify_admin(username, password):
            return None
        row = self.connection.execute(
            "SELECT * FROM admins WHERE username = ? LIMIT 1", (username,)
        ).fetchone()
        return self._redact_sensitive_values(dict(row)) if row else None

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def user_history(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def next_session_id(self) -> int:
        row = self.connection.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM sessions").fetchone()
        return int(row["next_id"])