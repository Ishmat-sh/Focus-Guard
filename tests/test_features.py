import pytest

from backend.features.schema import FEATURE_FIELDS, FEATURE_SCHEMA_VERSION, validate_feature_vector
from backend.features.windows import compute_window_features


def test_window_features_capture_temporal_ratios_and_head_variance() -> None:
    frames = [
        {
            "active_app_category": "productive" if index < 5 else "distracting",
            "app_switch_count": 1 if index == 5 else 0,
            "blink_rate_per_minute": float(index),
            "ear": 0.1 if index < 3 else 0.3,
            "face_present": index != 9,
            "gaze_offset_x": 0.1 * index,
            "gaze_offset_y": 0.0,
            "head_pitch_degrees": float(index),
            "head_roll_degrees": 0.0,
            "head_yaw_degrees": float(index),
            "looking_at_screen": index < 8,
            "posture_score": None,
        }
        for index in range(10)
    ]

    features = compute_window_features(frames, window_seconds=10)

    assert tuple(features) == FEATURE_FIELDS
    assert features["perclos"] == pytest.approx(0.3)
    assert features["face_missing_ratio"] == pytest.approx(0.1)
    assert features["gaze_away_ratio"] == pytest.approx(0.2)
    assert features["distracting_app_ratio"] == pytest.approx(0.5)
    assert features["active_app_category"] == "distracting"
    assert features["app_switches_per_minute"] == pytest.approx(6.0)
    assert features["head_yaw_mean_degrees"] == pytest.approx(4.5)
    assert features["head_yaw_std_degrees"] == pytest.approx(2.872281323)


def test_window_feature_validation_rejects_bad_schema_and_values() -> None:
    vector = {
        field: "unknown" if field == "active_app_category" else 0.0
        for field in FEATURE_FIELDS
    }
    vector["perclos"] = 1.1

    with pytest.raises(ValueError, match="between 0 and 1"):
        validate_feature_vector(vector)

    vector["perclos"] = 0.0
    vector["unversioned_feature"] = 1.0
    with pytest.raises(ValueError, match="do not match schema"):
        validate_feature_vector(vector)


def test_empty_or_invalid_window_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="At least one frame"):
        compute_window_features([], window_seconds=10)
    with pytest.raises(ValueError, match="greater than zero"):
        compute_window_features([{}], window_seconds=0)


def test_perclos_uses_observed_time_not_the_number_of_frames() -> None:
    frames = [
        {
            "active_app_category": "productive",
            "app_switch_count": 0,
            "ear": 0.1,
            "elapsed_seconds": 0.0,
            "face_present": True,
            "looking_at_screen": True,
        },
        {
            "active_app_category": "productive",
            "app_switch_count": 0,
            "ear": 0.3,
            "elapsed_seconds": 3.0,
            "face_present": True,
            "looking_at_screen": True,
        },
        {
            "active_app_category": "productive",
            "app_switch_count": 0,
            "ear": 0.3,
            "elapsed_seconds": 10.0,
            "face_present": True,
            "looking_at_screen": True,
        },
    ]

    features = compute_window_features(frames, window_seconds=10)

    assert features["perclos"] == pytest.approx(0.3)


def test_feature_contract_has_an_explicit_version() -> None:
    assert FEATURE_SCHEMA_VERSION == 1
