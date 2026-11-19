from pathlib import Path
from collections import deque

import pytest

import backend.main as main
from backend.features.schema import FEATURE_FIELDS
from backend.ml.focused import (
    FocusedBaselinePrediction,
    FocusedBaselineInference,
    FocusedTrainingRecord,
    _rotate_frame,
    train_focused_baseline,
    video_files,
)


def _features(variation: float = 0.0) -> dict[str, object]:
    values = {
        field: 0.0
        for field in FEATURE_FIELDS
        if field != "active_app_category"
    }
    values["active_app_category"] = "unknown"
    values["ear_mean"] = 0.3 + variation
    values["head_yaw_mean_degrees"] = variation
    return values


def test_focused_baseline_trains_and_holds_out_whole_participants(tmp_path) -> None:
    records = [
        FocusedTrainingRecord(
            participant_id=f"participant-{participant}",
            clip_id=f"clip-{participant}-{window}",
            features=_features((participant % 3) * 0.01 + window * 0.001),
        )
        for participant in range(10)
        for window in range(4)
    ]

    report = train_focused_baseline(records, tmp_path / "models")

    assert report["model_type"] == "one_class_focused_baseline"
    assert report["training_target"] == "focused_only"
    assert report["nonfocused_examples"] == 0
    assert report["nonfocused_detection_metrics"] is None
    assert report["participant_splits_disjoint"] is True
    assert report["heldout_participants"] > 0
    model = FocusedBaselineInference(report["model_path"])
    prediction = model.predict(records[0].features)
    assert isinstance(prediction.matches_focused_baseline, bool)
    assert isinstance(prediction.normality_score, float)


def test_video_discovery_ignores_nested_virtual_environments(tmp_path) -> None:
    dataset = tmp_path / "dataset"
    recording = dataset / "Fold1" / "01" / "0.MOV"
    nested_environment_video = dataset / "Fold1" / "venv" / "ignored.mp4"
    recording.parent.mkdir(parents=True)
    nested_environment_video.parent.mkdir(parents=True)
    recording.touch()
    nested_environment_video.touch()

    assert video_files(dataset) == [recording]


def test_focused_training_requires_multiple_participants(tmp_path) -> None:
    records = [
        FocusedTrainingRecord("one", f"clip-{index}", _features())
        for index in range(10)
    ]

    with pytest.raises(ValueError, match="five distinct participants"):
        train_focused_baseline(records, tmp_path / "models")


def test_recording_rotation_metadata_is_applied_before_feature_extraction() -> None:
    import cv2
    import numpy as np

    frame = np.array([[1, 2, 3], [4, 5, 6]])

    rotated = _rotate_frame(frame, 90, cv2)

    assert rotated.tolist() == [[4, 1], [5, 2], [6, 3]]


def test_live_focused_baseline_exposes_only_match_or_deviation(monkeypatch) -> None:
    class FakeModel:
        def predict(self, features):
            assert features["active_app_category"] == "unknown"
            return FocusedBaselinePrediction(True, -0.37)

    monkeypatch.setattr(main, "_focused_baseline_for", lambda user_id: FakeModel())
    samples = deque(
        {
            "active_app_category": "unknown",
            "app_switch_count": 0.0,
            "blink_rate_per_minute": 0.0,
            "ear": 0.3,
            "elapsed_seconds": second,
            "face_present": True,
            "gaze_offset_x": 0.0,
            "gaze_offset_y": 0.0,
            "head_pitch_degrees": 0.0,
            "head_roll_degrees": 0.0,
            "head_yaw_degrees": 0.0,
            "looking_at_screen": True,
            "posture_score": None,
        }
        for second in range(11)
    )

    status, normality_score, error = main._focused_baseline_prediction_for(
        123, 10.0, samples
    )

    assert status == "matches_focused_baseline"
    assert normality_score == -0.37
    assert error is None
