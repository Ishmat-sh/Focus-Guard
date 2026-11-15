from datetime import date, datetime, timedelta, timezone

import pytest

from backend.analytics.service import (
    build_heatmap,
    build_streaks,
    build_weekly_analytics,
    refresh_user_analytics,
)
from backend.core.scoring import AttentionResult, AttentionState
from backend.core.session import Session, SessionState
from backend.storage.database import Database


def _result(score: float, state: AttentionState, app: str, category: str) -> AttentionResult:
    return AttentionResult(score, state, score, app, category)


def test_analytics_refresh_matches_seeded_telemetry_and_user_scope(tmp_path) -> None:
    database = Database(tmp_path / "analytics.db")
    owner = database.create_user("Owner", "owner@example.com", "safe-password")
    other = database.create_user("Other", "other@example.com", "safe-password")
    session = Session(1, SessionState.COMPLETED, 100.0, 130.0, 30.0)
    database.save_session(session, owner["id"])
    database.save_session(
        Session(2, SessionState.COMPLETED, 100.0, 130.0, 30.0),
        other["id"],
    )
    start = datetime(2025, 3, 3, 10, 0, tzinfo=timezone.utc).timestamp()
    samples = [
        (0.0, 80.0, AttentionState.FOCUSED, "Code", "productive"),
        (10.0, 80.0, AttentionState.FOCUSED, "Code", "productive"),
        (20.0, 40.0, AttentionState.DISTRACTED, "YouTube", "distracting"),
        (30.0, 80.0, AttentionState.FOCUSED, "Code", "productive"),
    ]
    for offset, score, state, app_name, category in samples:
        database.save_telemetry(
            1,
            start + offset,
            _result(score, state, app_name, category),
            True,
            elapsed_seconds=offset,
        )
    refresh_user_analytics(database, owner["id"])
    refresh_user_analytics(database, other["id"])

    weekly = build_weekly_analytics(
        database,
        owner["id"],
        date(2025, 3, 3),
        date(2025, 3, 9),
    )
    heatmap = build_heatmap(
        database,
        owner["id"],
        date(2025, 3, 3),
        date(2025, 3, 9),
    )
    streaks = build_streaks(
        database,
        owner["id"],
        date(2025, 3, 3),
        date(2025, 3, 9),
        minimum_seconds=5,
    )

    assert weekly["daily"][0]["total_focus_seconds"] == pytest.approx(20)
    assert weekly["daily"][0]["average_score"] == pytest.approx(200 / 3)
    assert weekly["daily"][0]["distraction_count"] == 1
    assert weekly["daily"][0]["session_count"] == 1
    assert weekly["comparison"]["current"]["total_focus_seconds"] == pytest.approx(20)
    assert weekly["comparison"]["change"]["total_focus_seconds"] is None
    populated = [cell for cell in heatmap["cells"] if cell["sample_count"]]
    assert len(populated) == 1
    assert populated[0]["day_of_week"] == 0
    assert populated[0]["hour"] == 10
    assert populated[0]["focus_seconds"] == pytest.approx(20)
    assert len(streaks["streaks"]) == 1
    assert streaks["longest_streak_seconds"] == pytest.approx(20)
    assert streaks["latest_streak_seconds"] == pytest.approx(20)
    assert all(cell["average_score"] is None for cell in heatmap["cells"] if not cell["sample_count"])
    assert database.analytics_rows(other["id"], "2025-03-03", "2025-03-09")["daily"] == []


def test_analytics_rebuild_is_idempotent(tmp_path) -> None:
    database = Database(tmp_path / "analytics.db")
    user = database.create_user("Owner", "owner@example.com", "safe-password")
    database.save_session(
        Session(1, SessionState.COMPLETED, 100.0, 110.0, 10.0),
        user["id"],
    )
    start = datetime(2025, 3, 3, 10, 0, tzinfo=timezone.utc).timestamp()
    for offset in (0, 10):
        database.save_telemetry(
            1,
            start + offset,
            _result(90, AttentionState.FOCUSED, "Editor", "productive"),
            True,
            elapsed_seconds=offset,
        )

    refresh_user_analytics(database, user["id"])
    refresh_user_analytics(database, user["id"])

    assert database.connection.execute("SELECT COUNT(*) FROM focus_streaks").fetchone()[0] == 1
    assert database.connection.execute("SELECT COUNT(*) FROM daily_summaries").fetchone()[0] == 1
