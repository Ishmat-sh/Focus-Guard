from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from pathlib import Path
from time import time
from typing import Any

from backend.context.categories import categorize_application
from backend.features.schema import FEATURE_SCHEMA_VERSION, validate_feature_vector


class Database:
    _PASSWORD_ITERATIONS = 310_000
    SCHEMA_VERSION = 3

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
        self._migrate_phase2_schema()
        self.connection.commit()

    def _migrate_phase2_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at REAL NOT NULL
            )
            """
        )
        applied = {
            int(row["version"])
            for row in self.connection.execute("SELECT version FROM schema_migrations")
        }
        if self.SCHEMA_VERSION in applied:
            return

        telemetry_columns = {
            row["name"] for row in self.connection.execute("PRAGMA table_info(telemetry)")
        }
        if "elapsed_seconds" not in telemetry_columns:
            self.connection.execute(
                "ALTER TABLE telemetry ADD COLUMN elapsed_seconds REAL"
            )
        if "features_json" not in telemetry_columns:
            self.connection.execute(
                "ALTER TABLE telemetry ADD COLUMN features_json TEXT"
            )
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS collection_consents (
                session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
                consented_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feature_windows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                start_elapsed_seconds REAL NOT NULL,
                end_elapsed_seconds REAL NOT NULL,
                schema_version INTEGER NOT NULL,
                features_json TEXT NOT NULL,
                created_at REAL NOT NULL,
                UNIQUE(session_id, start_elapsed_seconds),
                CHECK(start_elapsed_seconds >= 0),
                CHECK(end_elapsed_seconds > start_elapsed_seconds)
            );
            CREATE TABLE IF NOT EXISTS labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                start_elapsed_seconds REAL NOT NULL,
                end_elapsed_seconds REAL NOT NULL,
                label TEXT NOT NULL CHECK(
                    label IN ('focused', 'drifting', 'distracted', 'fatigued')
                ),
                source TEXT NOT NULL DEFAULT 'self_reported' CHECK(
                    source IN ('self_reported', 'rule_based', 'imported')
                ),
                created_at REAL NOT NULL,
                CHECK(start_elapsed_seconds >= 0),
                CHECK(end_elapsed_seconds > start_elapsed_seconds)
            );
            CREATE TABLE IF NOT EXISTS model_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                trained_at REAL,
                metrics_json TEXT,
                file_path TEXT,
                is_active INTEGER NOT NULL DEFAULT 0 CHECK(is_active IN (0, 1)),
                UNIQUE(name, version)
            );
            CREATE TABLE IF NOT EXISTS user_privacy_settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                retention_days INTEGER CHECK(
                    retention_days IS NULL OR retention_days BETWEEN 1 AND 3650
                )
            );
            CREATE TABLE IF NOT EXISTS daily_summaries (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                summary_date TEXT NOT NULL,
                total_focus_seconds REAL NOT NULL,
                observed_seconds REAL NOT NULL,
                average_score REAL,
                distraction_count INTEGER NOT NULL,
                session_count INTEGER NOT NULL,
                PRIMARY KEY (user_id, summary_date)
            );
            CREATE TABLE IF NOT EXISTS hourly_activity (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                activity_date TEXT NOT NULL,
                hour_utc INTEGER NOT NULL CHECK(hour_utc BETWEEN 0 AND 23),
                average_score REAL,
                focus_seconds REAL NOT NULL,
                sample_count INTEGER NOT NULL,
                PRIMARY KEY (user_id, activity_date, hour_utc)
            );
            CREATE TABLE IF NOT EXISTS focus_streaks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                started_at REAL NOT NULL,
                ended_at REAL NOT NULL,
                duration_seconds REAL NOT NULL,
                UNIQUE(session_id, started_at)
            );
            CREATE TABLE IF NOT EXISTS app_usage (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                usage_date TEXT NOT NULL,
                app_name TEXT NOT NULL,
                app_category TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                PRIMARY KEY (user_id, usage_date, app_name, app_category)
            );
            CREATE TABLE IF NOT EXISTS app_category_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                rule_type TEXT NOT NULL CHECK(rule_type IN ('app', 'domain')),
                rule_value TEXT NOT NULL,
                category TEXT NOT NULL CHECK(
                    category IN ('productive', 'neutral', 'distracting')
                ),
                UNIQUE(user_id, rule_type, rule_value)
            );
            CREATE TABLE IF NOT EXISTS browser_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                recorded_at REAL NOT NULL,
                elapsed_seconds REAL NOT NULL,
                domain TEXT NOT NULL,
                category TEXT NOT NULL CHECK(
                    category IN ('productive', 'neutral', 'distracting', 'unknown')
                )
            );
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                insight_type TEXT NOT NULL,
                message TEXT NOT NULL,
                generated_at REAL NOT NULL,
                dismissed INTEGER NOT NULL DEFAULT 0 CHECK(dismissed IN (0, 1)),
                source TEXT NOT NULL DEFAULT 'rules' CHECK(source IN ('rules', 'ai')),
                UNIQUE(session_id, insight_type)
            );
            CREATE TABLE IF NOT EXISTS biometrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                recorded_at REAL NOT NULL,
                heart_rate REAL NOT NULL CHECK(heart_rate > 0),
                hrv REAL CHECK(hrv IS NULL OR hrv >= 0),
                source_device TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_browser_context_session_time
                ON browser_context(session_id, recorded_at);
            CREATE INDEX IF NOT EXISTS idx_insights_user_session
                ON insights(user_id, session_id, dismissed);
            CREATE INDEX IF NOT EXISTS idx_telemetry_session_elapsed
                ON telemetry(session_id, elapsed_seconds);
            CREATE INDEX IF NOT EXISTS idx_labels_session_range
                ON labels(session_id, start_elapsed_seconds, end_elapsed_seconds);
            """
        )
        self.connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (self.SCHEMA_VERSION, time()),
        )

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

    def save_telemetry(
        self,
        session_id: int,
        recorded_at: float,
        result: Any,
        face_present: bool,
        elapsed_seconds: float | None = None,
        features: dict[str, Any] | None = None,
    ) -> None:
        if features is not None and not self.collection_is_consented(session_id):
            raise ValueError("Feature collection requires session consent")
        self.connection.execute(
            """
            INSERT INTO telemetry (
                session_id, recorded_at, score, state, app_name, app_category,
                face_present, elapsed_seconds, features_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                recorded_at,
                result.score,
                result.state.value,
                result.app_name,
                result.app_category,
                int(face_present),
                elapsed_seconds,
                json.dumps(features, separators=(",", ":"), sort_keys=True)
                if features is not None
                else None,
            ),
        )
        self.connection.commit()

    def session_for_user(self, session_id: int, user_id: int) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        return dict(row) if row else None

    def session_owner(self, session_id: int) -> int | None:
        row = self.connection.execute(
            "SELECT user_id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return int(row["user_id"]) if row and row["user_id"] is not None else None

    def telemetry_for_user(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT telemetry.session_id, telemetry.recorded_at,
                   telemetry.elapsed_seconds, telemetry.score, telemetry.state,
                   telemetry.app_name, telemetry.app_category
            FROM telemetry
            JOIN sessions ON sessions.id = telemetry.session_id
            WHERE sessions.user_id = ?
            ORDER BY telemetry.session_id, telemetry.recorded_at, telemetry.id
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def upsert_category_rule(
        self, user_id: int, rule_type: str, rule_value: str, category: str
    ) -> dict[str, Any]:
        if rule_type not in {"app", "domain"}:
            raise ValueError("rule_type must be 'app' or 'domain'")
        if category not in {"productive", "neutral", "distracting"}:
            raise ValueError("Unsupported application category")
        self.connection.execute(
            """
            INSERT INTO app_category_rules (user_id, rule_type, rule_value, category)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, rule_type, rule_value) DO UPDATE SET
                category = excluded.category
            """,
            (user_id, rule_type, rule_value, category),
        )
        self.connection.commit()
        row = self.connection.execute(
            """
            SELECT id, rule_type, rule_value, category
            FROM app_category_rules
            WHERE user_id = ? AND rule_type = ? AND rule_value = ?
            """,
            (user_id, rule_type, rule_value),
        ).fetchone()
        return dict(row)

    def category_rules(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, rule_type, rule_value, category
            FROM app_category_rules WHERE user_id = ?
            ORDER BY rule_type, rule_value
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def delete_category_rule(self, user_id: int, rule_id: int) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM app_category_rules WHERE user_id = ? AND id = ?",
            (user_id, rule_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def category_for_application(self, user_id: int, app_name: str) -> str:
        row = self.connection.execute(
            """
            SELECT category FROM app_category_rules
            WHERE user_id = ? AND rule_type = 'app' AND rule_value = ? COLLATE NOCASE
            """,
            (user_id, app_name.strip()),
        ).fetchone()
        return str(row["category"]) if row else "unknown"

    def category_for_domain(self, user_id: int, domain: str) -> str | None:
        rows = self.connection.execute(
            """
            SELECT rule_value, category FROM app_category_rules
            WHERE user_id = ? AND rule_type = 'domain'
            ORDER BY length(rule_value) DESC
            """,
            (user_id,),
        ).fetchall()
        normalized_domain = domain.casefold().rstrip(".")
        for row in rows:
            rule_domain = str(row["rule_value"]).casefold().rstrip(".")
            if normalized_domain == rule_domain or normalized_domain.endswith(
                "." + rule_domain
            ):
                return str(row["category"])
        return None

    def save_browser_context(
        self,
        session_id: int,
        domain: str,
        recorded_at: float,
        elapsed_seconds: float,
    ) -> dict[str, Any] | None:
        session = self.connection.execute(
            "SELECT id, user_id, state FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session is None or session["user_id"] is None or session["state"] != "running":
            return None
        user_id = int(session["user_id"])
        category = self.category_for_domain(user_id, domain)
        if category is None:
            category = categorize_application(domain).value
        cursor = self.connection.execute(
            """
            INSERT INTO browser_context (
                user_id, session_id, recorded_at, elapsed_seconds, domain, category
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, session_id, recorded_at, elapsed_seconds, domain, category),
        )
        self.connection.commit()
        return {
            "id": cursor.lastrowid,
            "session_id": session_id,
            "recorded_at": recorded_at,
            "elapsed_seconds": elapsed_seconds,
            "domain": domain,
            "category": category,
        }

    def latest_browser_context(
        self, user_id: int, session_id: int, now: float, max_age_seconds: float = 30.0
    ) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT recorded_at, elapsed_seconds, domain, category
            FROM browser_context
            WHERE user_id = ? AND session_id = ? AND recorded_at >= ?
            ORDER BY recorded_at DESC, id DESC LIMIT 1
            """,
            (user_id, session_id, now - max_age_seconds),
        ).fetchone()
        return dict(row) if row else None

    def replace_user_analytics(
        self,
        user_id: int,
        daily: list[dict[str, Any]],
        hourly: list[dict[str, Any]],
        streaks: list[dict[str, Any]],
        app_usage: list[dict[str, Any]],
    ) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM daily_summaries WHERE user_id = ?", (user_id,))
            self.connection.execute("DELETE FROM hourly_activity WHERE user_id = ?", (user_id,))
            self.connection.execute("DELETE FROM focus_streaks WHERE user_id = ?", (user_id,))
            self.connection.execute("DELETE FROM app_usage WHERE user_id = ?", (user_id,))
            self.connection.executemany(
                """
                INSERT INTO daily_summaries (
                    user_id, summary_date, total_focus_seconds, average_score,
                    observed_seconds, distraction_count, session_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        user_id,
                        row["date"],
                        row["total_focus_seconds"],
                        row["average_score"],
                        row["observed_seconds"],
                        row["distraction_count"],
                        row["session_count"],
                    )
                    for row in daily
                ],
            )
            self.connection.executemany(
                """
                INSERT INTO hourly_activity (
                    user_id, activity_date, hour_utc, average_score,
                    focus_seconds, sample_count
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        user_id,
                        row["date"],
                        row["hour"],
                        row["average_score"],
                        row["focus_seconds"],
                        row["sample_count"],
                    )
                    for row in hourly
                ],
            )
            self.connection.executemany(
                """
                INSERT INTO focus_streaks (
                    user_id, session_id, started_at, ended_at, duration_seconds
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        user_id,
                        row["session_id"],
                        row["started_at"],
                        row["ended_at"],
                        row["duration_seconds"],
                    )
                    for row in streaks
                ],
            )
            self.connection.executemany(
                """
                INSERT INTO app_usage (
                    user_id, usage_date, app_name, app_category, duration_seconds
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        user_id,
                        row["date"],
                        row["app_name"],
                        row["app_category"],
                        row["duration_seconds"],
                    )
                    for row in app_usage
                ],
            )

    def analytics_rows(
        self, user_id: int, start_date: str, end_date: str
    ) -> dict[str, list[dict[str, Any]]]:
        daily = self.connection.execute(
            """
            SELECT summary_date AS date, total_focus_seconds, observed_seconds, average_score,
                   distraction_count, session_count
            FROM daily_summaries
            WHERE user_id = ? AND summary_date BETWEEN ? AND ?
            ORDER BY summary_date
            """,
            (user_id, start_date, end_date),
        ).fetchall()
        hourly = self.connection.execute(
            """
            SELECT activity_date AS date, hour_utc AS hour, average_score,
                   focus_seconds, sample_count
            FROM hourly_activity
            WHERE user_id = ? AND activity_date BETWEEN ? AND ?
            ORDER BY activity_date, hour_utc
            """,
            (user_id, start_date, end_date),
        ).fetchall()
        app_usage = self.connection.execute(
            """
            SELECT app_name, app_category, SUM(duration_seconds) AS duration_seconds
            FROM app_usage
            WHERE user_id = ? AND usage_date BETWEEN ? AND ?
            GROUP BY app_name, app_category
            ORDER BY duration_seconds DESC, app_name
            """,
            (user_id, start_date, end_date),
        ).fetchall()
        streaks = self.connection.execute(
            """
            SELECT session_id, started_at, ended_at, duration_seconds
            FROM focus_streaks
            WHERE user_id = ? AND date(started_at, 'unixepoch') BETWEEN ? AND ?
            ORDER BY ended_at DESC, started_at DESC
            """,
            (user_id, start_date, end_date),
        ).fetchall()
        return {
            "daily": [dict(row) for row in daily],
            "hourly": [dict(row) for row in hourly],
            "app_usage": [dict(row) for row in app_usage],
            "streaks": [dict(row) for row in streaks],
        }

    def create_insight(
        self,
        user_id: int,
        session_id: int,
        insight_type: str,
        message: str,
        generated_at: float,
        source: str = "rules",
    ) -> dict[str, Any]:
        if source not in {"rules", "ai"}:
            raise ValueError("Unsupported insight source")
        self.connection.execute(
            """
            INSERT INTO insights (
                user_id, session_id, insight_type, message, generated_at, source
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, insight_type) DO UPDATE SET
                message = excluded.message,
                generated_at = excluded.generated_at,
                source = excluded.source
            """,
            (user_id, session_id, insight_type, message, generated_at, source),
        )
        self.connection.commit()
        row = self.connection.execute(
            """
            SELECT * FROM insights
            WHERE user_id = ? AND session_id = ? AND insight_type = ?
            """,
            (user_id, session_id, insight_type),
        ).fetchone()
        return dict(row)

    def insights_for_user(
        self, user_id: int, session_id: int | None = None
    ) -> list[dict[str, Any]]:
        if session_id is None:
            rows = self.connection.execute(
                """
                SELECT * FROM insights WHERE user_id = ?
                ORDER BY generated_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT * FROM insights WHERE user_id = ? AND session_id = ?
                ORDER BY generated_at, id
                """,
                (user_id, session_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def dismiss_insight(self, user_id: int, insight_id: int) -> bool:
        cursor = self.connection.execute(
            "UPDATE insights SET dismissed = 1 WHERE user_id = ? AND id = ?",
            (user_id, insight_id),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_session(self, session_id: int, user_id: int) -> bool:
        with self.connection:
            exists = self.connection.execute(
                "SELECT 1 FROM sessions WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if exists is None:
                return False
            self.connection.execute(
                "DELETE FROM telemetry WHERE session_id = ?", (session_id,)
            )
            self.connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return True

    def delete_all_user_data(self, user_id: int) -> int:
        with self.connection:
            session_ids = [
                row["id"]
                for row in self.connection.execute(
                    "SELECT id FROM sessions WHERE user_id = ?", (user_id,)
                )
            ]
            if session_ids:
                placeholders = ",".join("?" for _ in session_ids)
                self.connection.execute(
                    f"DELETE FROM telemetry WHERE session_id IN ({placeholders})",
                    session_ids,
                )
                self.connection.execute(
                    f"DELETE FROM sessions WHERE id IN ({placeholders})",
                    session_ids,
                )
            self.connection.execute(
                "DELETE FROM user_privacy_settings WHERE user_id = ?", (user_id,)
            )
            for table in (
                "daily_summaries",
                "hourly_activity",
                "app_usage",
                "app_category_rules",
            ):
                self.connection.execute(
                    f"DELETE FROM {table} WHERE user_id = ?", (user_id,)
                )
        return len(session_ids)

    def export_user_data(self, user_id: int) -> dict[str, Any]:
        sessions = self.connection.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
        exported_sessions: list[dict[str, Any]] = []
        for session in sessions:
            telemetry_rows = self.connection.execute(
                """
                SELECT id, recorded_at, elapsed_seconds, score, state,
                       app_name, app_category, face_present, features_json
                FROM telemetry WHERE session_id = ? ORDER BY recorded_at, id
                """,
                (session["id"],),
            ).fetchall()
            telemetry = []
            for row in telemetry_rows:
                data = dict(row)
                features_json = data.pop("features_json")
                data["features"] = (
                    json.loads(features_json)
                    if features_json is not None
                    else None
                )
                telemetry.append(data)
            label_rows = self.connection.execute(
                "SELECT * FROM labels WHERE session_id = ? ORDER BY start_elapsed_seconds, id",
                (session["id"],),
            ).fetchall()
            browser_rows = self.connection.execute(
                """
                SELECT id, recorded_at, elapsed_seconds, domain, category
                FROM browser_context WHERE session_id = ? ORDER BY recorded_at, id
                """,
                (session["id"],),
            ).fetchall()
            insight_rows = self.connection.execute(
                """
                SELECT id, insight_type, message, generated_at, dismissed, source
                FROM insights WHERE session_id = ? ORDER BY generated_at, id
                """,
                (session["id"],),
            ).fetchall()
            biometric_rows = self.connection.execute(
                """
                SELECT id, recorded_at, heart_rate, hrv, source_device
                FROM biometrics WHERE session_id = ? ORDER BY recorded_at, id
                """,
                (session["id"],),
            ).fetchall()
            window_rows = self.connection.execute(
                "SELECT * FROM feature_windows WHERE session_id = ? ORDER BY start_elapsed_seconds, id",
                (session["id"],),
            ).fetchall()
            windows = []
            for row in window_rows:
                data = dict(row)
                data["features"] = json.loads(data.pop("features_json"))
                windows.append(data)
            consented = self.collection_is_consented(session["id"], user_id)
            exported_sessions.append(
                dict(session)
                | {
                    "collection_consented": consented,
                    "telemetry": telemetry,
                    "labels": [dict(row) for row in label_rows],
                    "feature_windows": windows,
                    "browser_context": [dict(row) for row in browser_rows],
                    "insights": [dict(row) for row in insight_rows],
                    "biometrics": [dict(row) for row in biometric_rows],
                }
            )
        return {"exported_at": time(), "sessions": exported_sessions}

    def set_retention_days(self, user_id: int, retention_days: int | None) -> None:
        if retention_days is not None and not 1 <= retention_days <= 3650:
            raise ValueError("retention_days must be between 1 and 3650, or null")
        self.connection.execute(
            """
            INSERT INTO user_privacy_settings (user_id, retention_days)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                retention_days = excluded.retention_days
            """,
            (user_id, retention_days),
        )
        self.connection.commit()

    def retention_days(self, user_id: int) -> int | None:
        row = self.connection.execute(
            "SELECT retention_days FROM user_privacy_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return int(row["retention_days"]) if row and row["retention_days"] else None

    def apply_retention_policy(self, user_id: int, now: float | None = None) -> int:
        days = self.retention_days(user_id)
        if days is None:
            return 0
        cutoff = (time() if now is None else now) - days * 86_400
        with self.connection:
            self.connection.execute(
                """
                DELETE FROM feature_windows
                WHERE created_at < ?
                  AND session_id IN (SELECT id FROM sessions WHERE user_id = ?)
                """,
                (cutoff, user_id),
            )
            self.connection.execute(
                """
                DELETE FROM labels
                WHERE created_at < ?
                  AND session_id IN (SELECT id FROM sessions WHERE user_id = ?)
                """,
                (cutoff, user_id),
            )
            self.connection.execute(
                """
                DELETE FROM browser_context
                WHERE recorded_at < ?
                  AND user_id = ?
                """,
                (cutoff, user_id),
            )
            self.connection.execute(
                """
                DELETE FROM biometrics
                WHERE recorded_at < ?
                  AND session_id IN (SELECT id FROM sessions WHERE user_id = ?)
                """,
                (cutoff, user_id),
            )
            self.connection.execute(
                """
                DELETE FROM insights
                WHERE generated_at < ?
                  AND user_id = ?
                """,
                (cutoff, user_id),
            )
            cursor = self.connection.execute(
                """
                DELETE FROM telemetry
                WHERE recorded_at < ?
                  AND session_id IN (SELECT id FROM sessions WHERE user_id = ?)
                """,
                (cutoff, user_id),
            )
        return cursor.rowcount

    def set_collection_consent(
        self, session_id: int, user_id: int, consented: bool
    ) -> bool:
        if self.session_for_user(session_id, user_id) is None:
            return False
        if consented:
            self.connection.execute(
                """
                INSERT INTO collection_consents (session_id, consented_at)
                VALUES (?, ?)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id, time()),
            )
        else:
            self.connection.execute(
                "DELETE FROM collection_consents WHERE session_id = ?", (session_id,)
            )
            self.connection.execute(
                "DELETE FROM feature_windows WHERE session_id = ?", (session_id,)
            )
            self.connection.execute("DELETE FROM labels WHERE session_id = ?", (session_id,))
            self.connection.execute(
                "UPDATE telemetry SET features_json = NULL WHERE session_id = ?",
                (session_id,),
            )
        self.connection.commit()
        return True

    def collection_is_consented(self, session_id: int, user_id: int | None = None) -> bool:
        query = """
            SELECT 1 FROM collection_consents
            JOIN sessions ON sessions.id = collection_consents.session_id
            WHERE collection_consents.session_id = ?
        """
        parameters: tuple[int, ...] = (session_id,)
        if user_id is not None:
            query += " AND sessions.user_id = ?"
            parameters += (user_id,)
        return self.connection.execute(query, parameters).fetchone() is not None

    def create_label(
        self,
        session_id: int,
        user_id: int,
        start_elapsed_seconds: float,
        end_elapsed_seconds: float,
        label: str,
    ) -> dict[str, Any]:
        if not self.collection_is_consented(session_id, user_id):
            raise ValueError("Data collection consent is required for this session")
        cursor = self.connection.execute(
            """
            INSERT INTO labels (
                session_id, start_elapsed_seconds, end_elapsed_seconds,
                label, source, created_at
            ) VALUES (?, ?, ?, ?, 'self_reported', ?)
            """,
            (session_id, start_elapsed_seconds, end_elapsed_seconds, label, time()),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT * FROM labels WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return dict(row)

    def labels_for_session(self, session_id: int, user_id: int) -> list[dict[str, Any]]:
        if not self.collection_is_consented(session_id, user_id):
            raise ValueError("Data collection consent is required for this session")
        rows = self.connection.execute(
            "SELECT * FROM labels WHERE session_id = ? ORDER BY start_elapsed_seconds, id",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_feature_window(
        self,
        session_id: int,
        start_elapsed_seconds: float,
        end_elapsed_seconds: float,
        features: dict[str, object],
    ) -> None:
        validated = validate_feature_vector(features)
        if not self.collection_is_consented(session_id):
            raise ValueError("Feature collection requires session consent")
        self.connection.execute(
            """
            INSERT INTO feature_windows (
                session_id, start_elapsed_seconds, end_elapsed_seconds,
                schema_version, features_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, start_elapsed_seconds) DO UPDATE SET
                end_elapsed_seconds = excluded.end_elapsed_seconds,
                schema_version = excluded.schema_version,
                features_json = excluded.features_json,
                created_at = excluded.created_at
            """,
            (
                session_id,
                start_elapsed_seconds,
                end_elapsed_seconds,
                FEATURE_SCHEMA_VERSION,
                json.dumps(validated, separators=(",", ":"), sort_keys=True),
                time(),
            ),
        )
        self.connection.commit()

    def feature_samples(self, session_id: int, user_id: int) -> list[dict[str, Any]]:
        if not self.collection_is_consented(session_id, user_id):
            raise ValueError("Data collection consent is required for this session")
        rows = self.connection.execute(
            """
            SELECT elapsed_seconds, features_json
            FROM telemetry
            WHERE session_id = ? AND features_json IS NOT NULL
              AND elapsed_seconds IS NOT NULL
            ORDER BY elapsed_seconds, id
            """,
            (session_id,),
        ).fetchall()
        return [
            {"elapsed_seconds": row["elapsed_seconds"], **json.loads(row["features_json"])}
            for row in rows
        ]

    def feature_windows_for_session(
        self, session_id: int, user_id: int
    ) -> list[dict[str, Any]]:
        if not self.collection_is_consented(session_id, user_id):
            raise ValueError("Data collection consent is required for this session")
        rows = self.connection.execute(
            """
            SELECT * FROM feature_windows
            WHERE session_id = ?
            ORDER BY start_elapsed_seconds, id
            """,
            (session_id,),
        ).fetchall()
        return [
            dict(row) | {"features": json.loads(row["features_json"])}
            for row in rows
        ]

    def register_model_version(
        self,
        name: str,
        version: str,
        metrics: dict[str, Any],
        file_path: str,
        trained_at: float,
    ) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE model_versions SET is_active = 0 WHERE name = ?", (name,)
            )
            self.connection.execute(
                """
                INSERT INTO model_versions (
                    name, version, trained_at, metrics_json, file_path, is_active
                ) VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(name, version) DO UPDATE SET
                    trained_at = excluded.trained_at,
                    metrics_json = excluded.metrics_json,
                    file_path = excluded.file_path,
                    is_active = 1
                """,
                (
                    name,
                    version,
                    trained_at,
                    json.dumps(
                        metrics,
                        separators=(",", ":"),
                        sort_keys=True,
                        allow_nan=False,
                    ),
                    file_path,
                ),
            )

    def active_model_version(self, name: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM model_versions WHERE name = ? AND is_active = 1",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return dict(row) | {"metrics": json.loads(row["metrics_json"])}

    def labeled_feature_windows(
        self, session_id: int, user_id: int
    ) -> list[dict[str, Any]]:
        windows = self.feature_windows_for_session(session_id, user_id)
        labels = self.labels_for_session(session_id, user_id)
        dataset: list[dict[str, Any]] = []
        for window in windows:
            overlaps = [
                label
                for label in labels
                if min(window["end_elapsed_seconds"], label["end_elapsed_seconds"])
                > max(window["start_elapsed_seconds"], label["start_elapsed_seconds"])
            ]
            if not overlaps:
                continue
            selected = max(
                overlaps,
                key=lambda label: (
                    min(window["end_elapsed_seconds"], label["end_elapsed_seconds"])
                    - max(window["start_elapsed_seconds"], label["start_elapsed_seconds"]),
                    -label["id"],
                ),
            )
            dataset.append(window | {"label": selected["label"]})
        return dataset

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