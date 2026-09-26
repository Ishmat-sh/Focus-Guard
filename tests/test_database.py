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


def test_existing_sessions_table_gets_user_owner_column(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY,
            started_at REAL NOT NULL,
            ended_at REAL,
            elapsed_seconds REAL NOT NULL,
            state TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "INSERT INTO sessions VALUES (1, 10.0, 11.0, 1.0, 'completed')"
    )
    connection.commit()
    connection.close()

    database = Database(path)
    columns = {row["name"] for row in database.connection.execute("PRAGMA table_info(sessions)")}
    saved = database.connection.execute("SELECT * FROM sessions WHERE id = 1").fetchone()

    assert "user_id" in columns
    assert saved["user_id"] is None
    assert saved["elapsed_seconds"] == 1.0


def test_existing_users_table_gets_password_change_flag_without_locking_users(tmp_path) -> None:
    path = tmp_path / "legacy-users.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at REAL NOT NULL DEFAULT 100
        )
        """
    )
    connection.execute(
        "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
        ("Legacy User", "legacy@example.com", "legacy-password"),
    )
    connection.commit()
    connection.close()

    database = Database(path)
    user = database.verify_user("legacy@example.com", "legacy-password")

    assert user is not None
    assert user["must_change_password"] is False


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


def test_malformed_legacy_password_hash_is_rejected_safely() -> None:
    assert Database._verify_password("attempt", None) is False
    assert Database._verify_password("attempt", "pbkdf2_sha256$broken") is False


def test_duplicate_user_email_is_rejected(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    database.create_user("Alice", "alice@example.com", "secret123")

    try:
        database.create_user("Another Alice", "ALICE@example.com", "different")
    except ValueError as error:
        assert "already exists" in str(error)
    else:
        raise AssertionError("duplicate emails should not create another account")


def test_user_tokens_are_hashed_revocable_and_scoped(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    first = database.create_user("First", "first@example.com", "first-password")
    second = database.create_user("Second", "second@example.com", "second-password")
    first_token = database.issue_user_token(first["id"])
    second_token = database.issue_user_token(second["id"])

    assert database.get_user_for_token(first_token)["id"] == first["id"]
    assert database.get_user_for_token(second_token)["id"] == second["id"]
    stored_hash = database.connection.execute("SELECT token_hash FROM user_tokens").fetchone()[0]
    assert stored_hash != first_token

    database.revoke_user_token(first_token)
    assert database.get_user_for_token(first_token) is None
    assert database.get_user_for_token(second_token)["id"] == second["id"]


def test_delete_user_removes_tokens_sessions_and_telemetry(tmp_path) -> None:
    database = Database(tmp_path / "focus_guard.db")
    user = database.create_user("Delete Me", "delete@example.com", "safe-password")
    other_user = database.create_user("Keep Me", "keep@example.com", "safe-password")
    token = database.issue_user_token(user["id"])
    result = AttentionResult(65.0, AttentionState.DRIFTING, 65.0, "Unknown", "unknown")
    owned_session = Session(id=1, state=SessionState.RUNNING, started_at=100.0)
    other_session = Session(id=2, state=SessionState.RUNNING, started_at=100.0)
    database.save_session(owned_session, user["id"])
    database.save_session(other_session, other_user["id"])
    database.save_telemetry(owned_session.id, 101.0, result, True)
    database.save_telemetry(other_session.id, 101.0, result, False)

    assert database.delete_user(user["id"]) is True
    assert database.delete_user(user["id"]) is False
    assert database.get_user_for_token(token) is None
    assert database.user_history(user["id"]) == []
    assert database.user_history(other_user["id"])[0]["id"] == other_session.id
    assert database.connection.execute("SELECT COUNT(*) FROM telemetry").fetchone()[0] == 1


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

    assert {table["name"] for table in tables} == {
        "sessions", "telemetry", "users", "admins", "user_tokens"
    }
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