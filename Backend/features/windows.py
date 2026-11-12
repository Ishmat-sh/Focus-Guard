from __future__ import annotations

from collections import defaultdict
from math import isfinite, sqrt
from typing import Any

from backend.features.schema import FeatureVector, validate_feature_vector

EAR_CLOSED_THRESHOLD = 0.21


def compute_window_features(
    frames: list[dict[str, Any]],
    window_seconds: float,
    start_elapsed_seconds: float = 0.0,
) -> FeatureVector:
    """Aggregate derived frame measurements into one versioned training vector."""
    if not frames:
        raise ValueError("At least one frame is required")
    if not isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError("window_seconds must be greater than zero")

    if not isfinite(start_elapsed_seconds) or start_elapsed_seconds < 0:
        raise ValueError("start_elapsed_seconds must be finite and non-negative")
    weights = _sample_weights(frames, start_elapsed_seconds, window_seconds)
    total_weight = sum(weights)
    category_weights: dict[str, float] = defaultdict(float)
    latest_category: dict[str, int] = {}
    for index, (frame, weight) in enumerate(zip(frames, weights)):
        category = frame.get("active_app_category")
        if category in {"productive", "neutral", "distracting", "unknown"}:
            category_weights[category] += weight
            latest_category[category] = index
    category = None
    if category_weights:
        category = max(
            category_weights,
            key=lambda value: (category_weights[value], latest_category[value]),
        )
    ears = _numbers(frames, "ear")
    face_missing = sum(
        weight for frame, weight in zip(frames, weights)
        if not bool(frame.get("face_present", False))
    )
    gaze_away = sum(
        weight for frame, weight in zip(frames, weights)
        if not bool(frame.get("looking_at_screen", False))
    )
    distracting = sum(
        weight for frame, weight in zip(frames, weights)
        if frame.get("active_app_category") == "distracting"
    )
    switch_counts = _numbers(frames, "app_switch_count")
    if any(value < 0 or not value.is_integer() for value in switch_counts):
        raise ValueError("app_switch_count values must be non-negative integers")
    app_switches = sum(switch_counts)

    ear_weights = [
        weight for frame, weight in zip(frames, weights) if frame.get("ear") is not None
    ]
    posture_mean = _weighted_mean(frames, weights, "posture_score")
    return validate_feature_vector(
        {
            "ear_mean": _weighted_mean(frames, weights, "ear"),
            "ear_std": _weighted_std(frames, weights, "ear"),
            "blink_rate_per_minute": _weighted_mean(
                frames, weights, "blink_rate_per_minute"
            ),
            "perclos": sum(
                weight
                for frame, weight in zip(frames, weights)
                if frame.get("ear") is not None
                and float(frame["ear"]) < EAR_CLOSED_THRESHOLD
            )
            / sum(ear_weights)
            if ears and sum(ear_weights) > 0
            else None,
            "head_yaw_mean_degrees": _weighted_mean(
                frames, weights, "head_yaw_degrees"
            ),
            "head_yaw_std_degrees": _weighted_std(
                frames, weights, "head_yaw_degrees"
            ),
            "head_pitch_mean_degrees": _weighted_mean(
                frames, weights, "head_pitch_degrees"
            ),
            "head_pitch_std_degrees": _weighted_std(
                frames, weights, "head_pitch_degrees"
            ),
            "head_roll_mean_degrees": _weighted_mean(
                frames, weights, "head_roll_degrees"
            ),
            "head_roll_std_degrees": _weighted_std(
                frames, weights, "head_roll_degrees"
            ),
            "gaze_offset_x_mean": _weighted_mean(frames, weights, "gaze_offset_x"),
            "gaze_offset_y_mean": _weighted_mean(frames, weights, "gaze_offset_y"),
            "gaze_away_ratio": gaze_away / total_weight,
            "face_missing_ratio": face_missing / total_weight,
            "posture_score_mean": posture_mean,
            "active_app_category": category,
            "app_switches_per_minute": app_switches * 60.0 / window_seconds,
            "distracting_app_ratio": distracting / total_weight,
        }
    )


def _sample_weights(
    frames: list[dict[str, Any]],
    start_elapsed_seconds: float,
    window_seconds: float,
) -> list[float]:
    timestamps = [frame.get("elapsed_seconds") for frame in frames]
    if not all(
        isinstance(timestamp, (int, float))
        and not isinstance(timestamp, bool)
        and isfinite(timestamp)
        for timestamp in timestamps
    ):
        return [1.0] * len(frames)

    end = start_elapsed_seconds + window_seconds
    values = [float(timestamp) for timestamp in timestamps]
    weights = [
        max(0.0, (values[index + 1] if index + 1 < len(values) else end) - value)
        for index, value in enumerate(values)
    ]
    if sum(weights) == 0:
        return [1.0] * len(frames)
    return weights


def _weighted_mean(
    frames: list[dict[str, Any]], weights: list[float], field: str
) -> float | None:
    pairs = _numeric_pairs(frames, weights, field)
    total_weight = sum(weight for _, weight in pairs)
    if not pairs:
        return None
    if total_weight == 0:
        return sum(value for value, _ in pairs) / len(pairs)
    return sum(value * weight for value, weight in pairs) / total_weight


def _weighted_std(
    frames: list[dict[str, Any]], weights: list[float], field: str
) -> float | None:
    pairs = _numeric_pairs(frames, weights, field)
    if not pairs:
        return None
    total_weight = sum(weight for _, weight in pairs)
    if total_weight == 0:
        return _population_std([value for value, _ in pairs])
    mean = sum(value * weight for value, weight in pairs) / total_weight
    return sqrt(
        sum(weight * (value - mean) ** 2 for value, weight in pairs)
        / total_weight
    )


def _numeric_pairs(
    frames: list[dict[str, Any]], weights: list[float], field: str
) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for frame, weight in zip(frames, weights):
        value = frame.get(field)
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            raise ValueError(f"{field} values must be numeric or null")
        pairs.append((float(value), weight))
    return pairs


def _numbers(frames: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for frame in frames:
        value = frame.get(field)
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            raise ValueError(f"{field} values must be numeric or null")
        values.append(float(value))
    return values


def _population_std(values: list[float]) -> float | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    return sqrt(sum((value - mean) ** 2 for value in values) / len(values))
