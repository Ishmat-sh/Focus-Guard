import sqlite3

from backend.core.scoring import AttentionResult, AttentionState
from backend.core.session import Session, SessionManager, SessionState
from backend.storage.database import Database


def test_session_and_telemetry_are_persisted_without_raw_frames(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    session = Session(
        id=1,
        state=SessionState.RUNNING,
        started_at=100.0,
    )
    result = AttentionResult(82.0, AttentionState.FOCUSED, 82.0, "Code", "productive")

    database.save_session(session)
    database.save_telemetry(session.id, 101.0, result, True)
    session.elapsed_seconds = 1.0
    session.ended_at = 101.0
    session.state = SessionState.COMPLETED
    database.save_session(session)

    saved_session = database.connection.execute("SELECT * FROM sessions").fetchone()
    saved_telemetry = database.connection.execute("SELECT * FROM telemetry").fetchone()
    columns = {row[1] for row in database.connection.execute("PRAGMA table_info(telemetry)")}

    assert dict(saved_session)["state"] == "completed"
    assert dict(saved_telemetry)["session_id"] == 1
    assert dict(saved_telemetry)["face_present"] == 1
    assert "frame" not in columns
    assert "image" not in columns
    assert "raw_frame" not in columns


def test_telemetry_requires_an_existing_session(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    result = AttentionResult(50.0, AttentionState.DRIFTING, 50.0, "Unknown", "unknown")

    try:
        database.save_telemetry(99, 101.0, result, False)
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("telemetry should require an existing session")


def test_repeated_sessions_persist_duration_and_increment_id(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    now = [100.0]
    manager = SessionManager(clock=lambda: now[0], next_id=database.next_session_id)

    completed_sessions = []
    for duration in (17.0, 42.0):
        session = manager.start()
        database.save_session(session)
        now[0] += duration
        completed = manager.end()
        database.save_session(completed)
        completed_sessions.append(completed)

    history = database.history()
    assert [session.id for session in completed_sessions] == [1, 2]
    assert [session["id"] for session in history] == [2, 1]
    assert [session["elapsed_seconds"] for session in history] == [42.0, 17.0]


def test_users_and_admins_tables_are_created_and_returned(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")

    database.create_user("Alice", "alice@example.com", "secret")
    database.create_admin("admin", "admin123")

    users = database.list_users()
    admins = database.list_admins()

    assert any(user["email"] == "alice@example.com" for user in users)
    assert any(admin["username"] == "admin" for admin in admins)
    assert all(user["password"] == "[redacted]" for user in users)
    assert all(admin["password"] == "[redacted]" for admin in admins)
    stored_admin_password = database.connection.execute(
        "SELECT password FROM admins WHERE username = ?", ("admin",)
    ).fetchone()["password"]
    assert stored_admin_password.startswith("pbkdf2_sha256$")
    assert database.verify_admin("admin", "admin123") is True
    assert database.verify_admin("admin", "wrong") is False


def test_users_and_admins_are_persisted_in_database(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")

    created_user = database.create_user("Alice", "alice@example.com", "secret123")
    database.create_admin("admin", "admin123", "admin@example.com")

    users = database.get_users()
    admin = database.validate_admin("admin", "admin123")

    assert created_user["email"] == "alice@example.com"
    assert len(users) >= 1
    assert any(user["email"] == "alice@example.com" for user in users)
    assert admin is not None
    assert admin["username"] == "admin"


def test_user_passwords_are_hashed_and_verified(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    created = database.create_user("Alice", "Alice@Example.com", "secret123")
    stored_password = database.connection.execute(
        "SELECT password FROM users WHERE id = ?", (created["id"],)
    ).fetchone()["password"]

    assert created["email"] == "alice@example.com"
    assert stored_password != "secret123"
    assert stored_password.startswith("pbkdf2_sha256$")
    verified = database.verify_user("ALICE@example.com", "secret123")
    assert verified is not None
    assert verified["id"] == created["id"]
    assert database.verify_user("alice@example.com", "wrong") is None


def test_duplicate_user_email_is_rejected(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    database.create_user("Alice", "alice@example.com", "secret123")

    try:
        database.create_user("Another Alice", "ALICE@example.com", "different")
    except ValueError as error:
        assert "already exists" in str(error)
    else:
        raise AssertionError("duplicate emails should not create another account")


def test_legacy_plaintext_password_is_upgraded_on_successful_login(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    database.connection.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        ("Legacy", "legacy@example.com", "old-secret"),
    )
    database.connection.commit()

    assert database.verify_user("legacy@example.com", "old-secret") is not None
    stored = database.connection.execute(
        "SELECT password FROM users WHERE email = ?", ("legacy@example.com",)
    ).fetchone()["password"]
    assert stored.startswith("pbkdf2_sha256$")


def test_database_explorer_lists_tables_and_redacts_sensitive_columns(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    database.create_user("Alice", "alice@example.com", "secret123")

    tables = database.list_tables()
    users = database.inspect_table("users", limit=1)

    assert {table["name"] for table in tables} == {"sessions", "telemetry", "users", "admins"}
    assert users["total"] == 1
    assert users["rows"][0]["email"] == "alice@example.com"
    assert users["rows"][0]["password"] == "[redacted]"
    assert users["columns"][0]["primary_key"] is True


def test_database_explorer_rejects_unknown_tables(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")

    try:
        database.inspect_table('users"; DROP TABLE users; --')
    except ValueError as error:
        assert "Unknown table" in str(error)
    else:
        raise AssertionError("unknown tables should not be queryable")