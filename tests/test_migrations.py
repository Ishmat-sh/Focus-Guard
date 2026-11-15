import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


ROOT = Path(__file__).resolve().parents[1]


def _upgrade(database_path: Path) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")


def test_fresh_database_migrates_to_head_and_is_repeatable(tmp_path) -> None:
    path = tmp_path / "fresh.db"

    _upgrade(path)
    _upgrade(path)

    connection = sqlite3.connect(path)
    try:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert revision == "0004_analytics_precision"
        assert {
            "sessions",
            "telemetry",
            "feature_windows",
            "labels",
            "daily_summaries",
            "hourly_activity",
            "app_category_rules",
            "browser_context",
            "insights",
            "biometrics",
        } <= tables
    finally:
        connection.close()


def test_phase1_database_migration_preserves_existing_rows(tmp_path) -> None:
    path = tmp_path / "phase1.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at REAL NOT NULL DEFAULT 123
        );
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY,
            started_at REAL NOT NULL,
            ended_at REAL,
            elapsed_seconds REAL NOT NULL,
            state TEXT NOT NULL
        );
        CREATE TABLE telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            recorded_at REAL NOT NULL,
            score REAL NOT NULL,
            state TEXT NOT NULL,
            app_name TEXT,
            app_category TEXT,
            face_present INTEGER NOT NULL
        );
        INSERT INTO users (name, email, password)
        VALUES ('Legacy', 'legacy@example.com', 'existing-hash');
        INSERT INTO sessions VALUES (1, 100, 110, 10, 'completed');
        INSERT INTO telemetry (
            session_id, recorded_at, score, state, app_name, app_category, face_present
        ) VALUES (1, 101, 80, 'focused', 'Code', 'productive', 1);
        """
    )
    connection.commit()
    connection.close()

    _upgrade(path)

    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT name, email, password FROM users WHERE id = 1"
        ).fetchone() == ("Legacy", "legacy@example.com", "existing-hash")
        assert connection.execute(
            "SELECT id, elapsed_seconds, state FROM sessions WHERE id = 1"
        ).fetchone() == (1, 10.0, "completed")
        assert connection.execute(
            "SELECT session_id, score, state FROM telemetry WHERE id = 1"
        ).fetchone() == (1, 80.0, "focused")
        assert "user_id" in {
            row[1] for row in connection.execute("PRAGMA table_info(sessions)")
        }
        assert "features_json" in {
            row[1] for row in connection.execute("PRAGMA table_info(telemetry)")
        }
    finally:
        connection.close()
