import sqlite3

from backend.core.scoring import AttentionResult, AttentionState
from backend.core.session import Session, SessionState
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