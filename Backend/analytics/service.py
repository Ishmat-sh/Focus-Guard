from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any


MAX_SAMPLE_GAP_SECONDS = 30.0
FOCUSED_STATES = {"focused"}


def refresh_user_analytics(database: Any, user_id: int) -> None:
    rows = database.telemetry_for_user(user_id)
    daily: dict[str, dict[str, Any]] = {}
    hourly: dict[tuple[str, int], dict[str, Any]] = {}
    app_usage: dict[tuple[str, str, str], float] = defaultdict(float)
    streaks: list[dict[str, Any]] = []
    by_session: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        by_session[int(row["session_id"])].append(row)

    for session_id, samples in by_session.items():
        active_streak_start: float | None = None
        active_streak_end: float | None = None
        active_streak_seconds = 0.0
        previous_state: str | None = None
        previous_sample: dict[str, Any] | None = None

        for sample in samples:
            sample_date = _utc_datetime(float(sample["recorded_at"])).date().isoformat()
            day = daily.setdefault(
                sample_date,
                {
                    "date": sample_date,
                    "total_focus_seconds": 0.0,
                    "_weighted_score": 0.0,
                    "_score_seconds": 0.0,
                    "distraction_count": 0,
                    "session_count": 0,
                    "_sessions": set(),
                },
            )
            day["_sessions"].add(session_id)
            state = str(sample["state"])
            if state == "distracted" and previous_state != "distracted":
                day["distraction_count"] += 1

            if previous_sample is not None:
                wall_start = float(previous_sample["recorded_at"])
                wall_gap = float(sample["recorded_at"]) - wall_start
                elapsed_gap = (
                    float(sample["elapsed_seconds"])
                    - float(previous_sample["elapsed_seconds"])
                    if sample["elapsed_seconds"] is not None
                    and previous_sample["elapsed_seconds"] is not None
                    else wall_gap
                )
                duration = min(max(0.0, elapsed_gap), max(0.0, wall_gap))
                if 0 < wall_gap <= MAX_SAMPLE_GAP_SECONDS:
                    _add_interval(
                        daily,
                        hourly,
                        app_usage,
                        session_id,
                        wall_start,
                        duration,
                        float(previous_sample["score"]),
                        str(previous_sample["state"]),
                        str(previous_sample.get("app_name") or "Unknown"),
                        str(previous_sample.get("app_category") or "unknown"),
                    )

                    if previous_sample["state"] in FOCUSED_STATES and duration > 0:
                        if active_streak_start is None:
                            active_streak_start = wall_start
                            active_streak_seconds = 0.0
                        active_streak_seconds += duration
                        active_streak_end = wall_start + duration
                    elif active_streak_start is not None and active_streak_end is not None:
                        streaks.append(
                            {
                                "session_id": session_id,
                                "started_at": active_streak_start,
                                "ended_at": active_streak_end,
                                "duration_seconds": active_streak_seconds,
                            }
                        )
                        active_streak_start = None
                        active_streak_end = None
                        active_streak_seconds = 0.0
                elif active_streak_start is not None and active_streak_end is not None:
                    streaks.append(
                        {
                            "session_id": session_id,
                            "started_at": active_streak_start,
                            "ended_at": active_streak_end,
                            "duration_seconds": active_streak_seconds,
                        }
                    )
                    active_streak_start = None
                    active_streak_end = None
                    active_streak_seconds = 0.0

            previous_state = state
            previous_sample = sample

        if active_streak_start is not None and active_streak_end is not None:
            streaks.append(
                {
                    "session_id": session_id,
                    "started_at": active_streak_start,
                    "ended_at": active_streak_end,
                    "duration_seconds": active_streak_seconds,
                }
            )

    for day in daily.values():
        day["session_count"] = len(day.pop("_sessions"))
        score_seconds = day.pop("_score_seconds")
        weighted_score = day.pop("_weighted_score")
        day["observed_seconds"] = score_seconds
        day["average_score"] = (
            weighted_score / score_seconds if score_seconds > 0 else None
        )

    hourly_rows: list[dict[str, Any]] = []
    for (activity_date, hour), item in hourly.items():
        hourly_rows.append(
            {
                "date": activity_date,
                "hour": hour,
                "average_score": (
                    item["_weighted_score"] / item["_score_seconds"]
                    if item["_score_seconds"] > 0
                    else None
                ),
                "focus_seconds": item["focus_seconds"],
                "sample_count": item["sample_count"],
            }
        )

    app_rows = [
        {
            "date": usage_date,
            "app_name": app_name,
            "app_category": category,
            "duration_seconds": duration,
        }
        for (usage_date, app_name, category), duration in app_usage.items()
    ]
    database.replace_user_analytics(
        user_id,
        list(daily.values()),
        hourly_rows,
        streaks,
        app_rows,
    )


def build_weekly_analytics(
    database: Any,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    days = (end_date - start_date).days + 1
    current_rows = database.analytics_rows(
        user_id, start_date.isoformat(), end_date.isoformat()
    )
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    previous_rows = database.analytics_rows(
        user_id, previous_start.isoformat(), previous_end.isoformat()
    )
    current = _range_totals(current_rows["daily"])
    previous = _range_totals(previous_rows["daily"])
    current["average_focus_score"] = _weighted_average(current_rows["daily"])
    previous["average_focus_score"] = _weighted_average(previous_rows["daily"])
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": current_rows["daily"],
        "app_usage": current_rows["app_usage"],
        "comparison": {
            "previous_start_date": previous_start.isoformat(),
            "previous_end_date": previous_end.isoformat(),
            "current": current,
            "previous": previous,
            "change": {
                key: _percentage_change(current[key], previous[key])
                for key in ("total_focus_seconds", "distraction_count", "average_focus_score")
            },
        },
    }


def build_heatmap(
    database: Any,
    user_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    rows = database.analytics_rows(
        user_id, start_date.isoformat(), end_date.isoformat()
    )["hourly"]
    lookup = {
        (date.fromisoformat(row["date"]).weekday(), int(row["hour"])): row
        for row in rows
    }
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": "UTC",
        "cells": [
            {
                "day_of_week": weekday,
                "hour": hour,
                "average_score": lookup.get((weekday, hour), {}).get("average_score"),
                "focus_seconds": lookup.get((weekday, hour), {}).get("focus_seconds"),
                "sample_count": lookup.get((weekday, hour), {}).get("sample_count", 0),
            }
            for weekday in range(7)
            for hour in range(24)
        ],
    }


def build_streaks(
    database: Any,
    user_id: int,
    start_date: date,
    end_date: date,
    minimum_seconds: float,
) -> dict[str, Any]:
    rows = database.analytics_rows(
        user_id, start_date.isoformat(), end_date.isoformat()
    )["streaks"]
    qualifying = [
        row for row in rows if float(row["duration_seconds"]) >= minimum_seconds
    ]
    durations = [float(row["duration_seconds"]) for row in rows]
    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "minimum_seconds": minimum_seconds,
        "streaks": qualifying,
        "latest_streak_seconds": float(rows[0]["duration_seconds"]) if rows else 0.0,
        "longest_streak_seconds": max(durations, default=0.0),
    }


def _add_interval(
    daily: dict[str, dict[str, Any]],
    hourly: dict[tuple[str, int], dict[str, Any]],
    app_usage: dict[tuple[str, str, str], float],
    session_id: int,
    start_timestamp: float,
    duration: float,
    score: float,
    state: str,
    app_name: str,
    app_category: str,
) -> None:
    remaining = duration
    cursor = start_timestamp
    while remaining > 1e-9:
        current = _utc_datetime(cursor)
        day_key = current.date().isoformat()
        boundary = current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        segment = min(remaining, max(0.0, boundary.timestamp() - cursor))
        if segment <= 0:
            break
        day = daily.setdefault(
            day_key,
            {
                "date": day_key,
                "total_focus_seconds": 0.0,
                "_weighted_score": 0.0,
                "_score_seconds": 0.0,
                "distraction_count": 0,
                "session_count": 0,
                "_sessions": set(),
            },
        )
        day["_sessions"].add(session_id)
        day["_weighted_score"] += score * segment
        day["_score_seconds"] += segment
        if state == "focused":
            day["total_focus_seconds"] += segment
        hour_key = (day_key, current.hour)
        hour = hourly.setdefault(
            hour_key,
            {
                "_weighted_score": 0.0,
                "_score_seconds": 0.0,
                "focus_seconds": 0.0,
                "sample_count": 0,
            },
        )
        hour["_weighted_score"] += score * segment
        hour["_score_seconds"] += segment
        hour["sample_count"] += 1
        if state == "focused":
            hour["focus_seconds"] += segment
        app_usage[(day_key, app_name, app_category)] += segment
        cursor += segment
        remaining -= segment


def _utc_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, timezone.utc)


def _range_totals(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    return {
        "total_focus_seconds": sum(float(row["total_focus_seconds"]) for row in rows),
        "distraction_count": sum(int(row["distraction_count"]) for row in rows),
        "session_count": sum(int(row["session_count"]) for row in rows),
    }


def _weighted_average(rows: list[dict[str, Any]]) -> float | None:
    weighted_sum = 0.0
    total_weight = 0.0
    for row in rows:
        if row["average_score"] is None:
            continue
        weight = float(row["observed_seconds"])
        if weight <= 0:
            continue
        weighted_sum += float(row["average_score"]) * weight
        total_weight += weight
    return weighted_sum / total_weight if total_weight else None


def _percentage_change(current: float | int | None, previous: float | int | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return (float(current) - float(previous)) / float(previous) * 100.0
