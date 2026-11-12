"""Versioned training vector fields and units.

EAR and its standard deviation are unitless; blink rate and app switches are
per minute; PERCLOS, gaze-away, face-missing, and distracting-app values are
fractions from 0 to 1; head-pose values are degrees; gaze offsets are
normalized by eye distance or face height; posture score is 0 to 1.
"""

from __future__ import annotations

from math import isfinite
from typing import TypeAlias

FEATURE_SCHEMA_VERSION = 1

FEATURE_FIELDS = (
    "ear_mean",
    "ear_std",
    "blink_rate_per_minute",
    "perclos",
    "head_yaw_mean_degrees",
    "head_yaw_std_degrees",
    "head_pitch_mean_degrees",
    "head_pitch_std_degrees",
    "head_roll_mean_degrees",
    "head_roll_std_degrees",
    "gaze_offset_x_mean",
    "gaze_offset_y_mean",
    "gaze_away_ratio",
    "face_missing_ratio",
    "posture_score_mean",
    "active_app_category",
    "app_switches_per_minute",
    "distracting_app_ratio",
)

FeatureValue: TypeAlias = float | str | None
FeatureVector: TypeAlias = dict[str, FeatureValue]


def validate_feature_vector(features: dict[str, object]) -> FeatureVector:
    """Validate a version-1 window vector before persistence or model use."""
    missing = set(FEATURE_FIELDS) - features.keys()
    extra = features.keys() - set(FEATURE_FIELDS)
    if missing or extra:
        raise ValueError(
            f"Feature vector fields do not match schema v{FEATURE_SCHEMA_VERSION}: "
            f"missing={sorted(missing)}, extra={sorted(extra)}"
        )

    validated: FeatureVector = {}
    for field in FEATURE_FIELDS:
        value = features[field]
        if field == "active_app_category":
            if value is not None and (
                not isinstance(value, str)
                or value not in {"productive", "neutral", "distracting", "unknown"}
            ):
                raise ValueError("active_app_category is not a supported category")
            validated[field] = value
        elif value is None:
            validated[field] = None
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a number or null")
        else:
            number = float(value)
            if not isfinite(number):
                raise ValueError(f"{field} must be finite")
            validated[field] = number

    for field in (
        "perclos",
        "gaze_away_ratio",
        "face_missing_ratio",
        "distracting_app_ratio",
    ):
        value = validated[field]
        if value is not None and not 0.0 <= value <= 1.0:
            raise ValueError(f"{field} must be between 0 and 1")
    return validated
