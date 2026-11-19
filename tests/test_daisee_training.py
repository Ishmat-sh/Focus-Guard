import csv
from collections import deque

import pytest

import backend.main as main
from backend.features.schema import FEATURE_FIELDS
from backend.ml.daisee import (
    DaiseeEngagementInference,
    DaiseeEngagementRecord,
    load_split_labels,
    train_daisee_engagement_model,
)


def _features(level: int) -> dict[str, object]:
    values = {
        field: 0.0
        for field in FEATURE_FIELDS
        if field != "active_app_category"
    }
    values["active_app_category"] = "unknown"
    values["ear_mean"] = 0.2 + level * 0.15
    values["gaze_away_ratio"] = level / 3
    return values


def _records(split: str) -> list[DaiseeEngagementRecord]:
    return [
        DaiseeEngagementRecord(
            participant_id=f"{split}-{level}",
            clip_id=f"{split}/{level}.avi",
            engagement_level=level,
            features=_features(level),
        )
        for level in range(4)
    ]


def test_daisee_labels_preserve_original_engagement_levels(tmp_path) -> None:
    root = tmp_path / "DAiSEE"
    (root / "Labels").mkdir(parents=True)
    (root / "DataSet").mkdir()
    with (root / "Labels" / "TrainLabels.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["ClipID", "Boredom", "Engagement", "Confusion", "Frustration "])
        writer.writerow(["clip.avi", 0, 2, 0, 0])
    (root / "DataSet" / "Train.txt").write_text("clip.avi\n")

    assert load_split_labels(root, "Train") == {"clip.avi": 2}


def test_daisee_label_rejects_levels_outside_annotation_scale(tmp_path) -> None:
    root = tmp_path / "DAiSEE"
    (root / "Labels").mkdir(parents=True)
    (root / "DataSet").mkdir()
    (root / "Labels" / "TrainLabels.csv").write_text(
        "ClipID,Engagement\nclip.avi,4\n"
    )
    (root / "DataSet" / "Train.txt").write_text("clip.avi\n")

    with pytest.raises(ValueError, match="unsupported engagement level"):
        load_split_labels(root, "Train")


def test_daisee_training_uses_disjoint_splits_and_loadable_model(tmp_path) -> None:
    report = train_daisee_engagement_model(
        _records("train"),
        _records("validation"),
        _records("test"),
        tmp_path / "models",
    )

    assert report["training_target"] == "DAiSEE Engagement label, unchanged (0-3)"
    assert report["participant_splits_disjoint"] is True
    assert set(report["test_evaluation"]["per_level"]) == {"0", "1", "2", "3"}
    model = DaiseeEngagementInference(report["model_path"])
    assert model.predict(_features(2)) in {0, 1, 2, 3}


def test_daisee_training_rejects_participant_overlap(tmp_path) -> None:
    train = _records("train")
    validation = _records("validation")
    validation[0] = DaiseeEngagementRecord(
        participant_id=train[0].participant_id,
        clip_id="validation/0.avi",
        engagement_level=0,
        features=_features(0),
    )

    with pytest.raises(ValueError, match="participants overlap"):
        train_daisee_engagement_model(
            train,
            validation,
            _records("test"),
            tmp_path / "models",
        )


def test_live_daisee_prediction_waits_for_a_window_then_reports_level(monkeypatch) -> None:
    class FakeModel:
        def predict(self, features):
            return 3

    monkeypatch.setattr(main, "_daisee_engagement_model_for", lambda user_id: FakeModel())
    monkeypatch.setattr(main, "compute_window_features", lambda *args, **kwargs: {})
    samples = deque({"elapsed_seconds": second} for second in range(11))

    assert main._daisee_engagement_prediction_for(1, 9.0, samples) == (
        "warming_up",
        None,
        None,
    )
    assert main._daisee_engagement_prediction_for(1, 10.0, samples) == (
        "available",
        3,
        None,
    )
