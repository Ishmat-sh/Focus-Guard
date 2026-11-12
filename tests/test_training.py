import csv

import pytest

from backend.features.schema import FEATURE_FIELDS, FEATURE_SCHEMA_VERSION
from backend.ml.inference import ModelInference
from backend.ml.train import TrainingRecord, read_training_csv, train_and_evaluate


def _write_training_csv(path, rows) -> None:
    columns = [
        "session_id",
        "label",
        "feature_schema_version",
        *FEATURE_FIELDS,
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _valid_row(session_id: str = "session-1") -> dict[str, object]:
    return {
        "session_id": session_id,
        "label": "focused",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        **{
            field: "productive" if field == "active_app_category" else "0.5"
            for field in FEATURE_FIELDS
        },
    }


def test_training_loader_reads_only_schema_compatible_labeled_features(tmp_path) -> None:
    path = tmp_path / "labeled.csv"
    _write_training_csv(path, [_valid_row()])

    records = read_training_csv(path)

    assert len(records) == 1
    assert records[0].session_id == "session-1"
    assert records[0].label == "focused"
    assert records[0].features["active_app_category"] == "productive"
    assert records[0].features["ear_mean"] == 0.5


def test_training_loader_rejects_wrong_schema_and_unlabeled_rows(tmp_path) -> None:
    path = tmp_path / "invalid.csv"
    row = _valid_row()
    row["feature_schema_version"] = FEATURE_SCHEMA_VERSION + 1
    _write_training_csv(path, [row])

    with pytest.raises(ValueError, match="expected v"):
        read_training_csv(path)

    row = _valid_row()
    row["label"] = ""
    _write_training_csv(path, [row])
    with pytest.raises(ValueError, match="unsupported label"):
        read_training_csv(path)


def test_training_loader_rejects_missing_feature_columns(tmp_path) -> None:
    path = tmp_path / "missing.csv"
    _write_training_csv(path, [])
    text = path.read_text(encoding="utf-8").replace(",ear_mean", "")
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        read_training_csv(path)


def test_training_compares_baselines_with_sessions_held_out(tmp_path) -> None:
    records = []
    labels = ("focused", "drifting", "distracted", "fatigued")
    for index in range(20):
        label = labels[index % len(labels)]
        values = {
            field: 0.5
            for field in FEATURE_FIELDS
            if field != "active_app_category"
        }
        values["active_app_category"] = "productive"
        values["perclos"] = 0.1 if label == "focused" else 0.8
        features = {
            field: (
                values[field]
                if field in values
                else None
            )
            for field in FEATURE_FIELDS
        }
        records.append(TrainingRecord(f"session-{index}", label, features))

    report = train_and_evaluate(records, tmp_path / "models")

    held_out = set(report["candidate_models"]["logistic_regression"]["held_out_sessions"])
    assert report["split_strategy"] == "grouped_session_train_validation_test"
    assert report["train_rows"] + report["test_rows"] == len(records)
    assert 0 < report["validation_rows"] < report["train_rows"]
    assert len(held_out) == report["test_rows"]
    assert report["selected_model"] in {"logistic_regression", "random_forest"}
    assert (
        tmp_path / "models" / f"{report['selected_model']}.joblib"
    ).exists()
    prediction = ModelInference(report["model_path"]).predict(records[0].features)
    assert 0.0 <= prediction.confidence <= 1.0
    assert prediction.state.value in {"focused", "drifting", "distracted", "fatigued"}
    assert prediction.inference_ms >= 0
