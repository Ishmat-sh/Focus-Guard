"""Offline baseline training.

Run with: python -m backend.ml.train labeled_sessions.csv
The input CSV is created by the authenticated session dataset-export endpoint.
No training data is bundled with this module.

Set FOCUS_GUARD_SCORER=ml to use the registered model in the API. The rules
scorer remains active until a compatible model is trained and registered.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.scoring import AttentionScorer, VisionSignals
from backend.features.schema import (
    FEATURE_FIELDS,
    FEATURE_SCHEMA_VERSION,
    FeatureVector,
    validate_feature_vector,
)
from backend.storage.database import Database

LABELS = ("focused", "drifting", "distracted", "fatigued")
GROUP_FIELD = "session_id"
REQUIRED_COLUMNS = {
    GROUP_FIELD,
    "label",
    "feature_schema_version",
    *FEATURE_FIELDS,
}


@dataclass(frozen=True)
class TrainingRecord:
    session_id: str
    label: str
    features: FeatureVector


def read_training_csv(path: str | Path) -> list[TrainingRecord]:
    records: list[TrainingRecord] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("Training CSV is missing its header row")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Training CSV is missing columns: {sorted(missing)}")
        for line_number, row in enumerate(reader, start=2):
            session_id = (row.get(GROUP_FIELD) or "").strip()
            label = (row.get("label") or "").strip()
            if not session_id:
                raise ValueError(f"Row {line_number} has no session_id")
            if label not in LABELS:
                raise ValueError(f"Row {line_number} has an unsupported label")
            try:
                schema_version = int(row["feature_schema_version"])
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"Row {line_number} has an invalid feature schema version"
                ) from error
            if schema_version != FEATURE_SCHEMA_VERSION:
                raise ValueError(
                    f"Row {line_number} uses feature schema v{schema_version}; "
                    f"expected v{FEATURE_SCHEMA_VERSION}"
                )
            features = _parse_feature_row(row, line_number)
            records.append(TrainingRecord(session_id, label, features))
    if not records:
        raise ValueError("Training CSV contains no labeled feature windows")
    return records


def _parse_feature_row(row: dict[str, str], line_number: int) -> FeatureVector:
    values: dict[str, object] = {}
    for field in FEATURE_FIELDS:
        raw = (row.get(field) or "").strip()
        if field == "active_app_category":
            values[field] = raw or None
        elif not raw:
            values[field] = None
        else:
            try:
                values[field] = float(raw)
            except ValueError as error:
                raise ValueError(
                    f"Row {line_number} has a non-numeric value for {field}"
                ) from error
    try:
        return validate_feature_vector(values)
    except ValueError as error:
        raise ValueError(f"Row {line_number}: {error}") from error


def train_and_evaluate(
    records: list[TrainingRecord],
    output_dir: str | Path,
) -> dict[str, Any]:
    if len({record.session_id for record in records}) < 5:
        raise ValueError(
            "At least five labeled sessions are required for separate "
            "training, validation, and test groups"
        )
    if len({record.label for record in records}) < 2:
        raise ValueError("At least two distinct labels are required for model training")
    try:
        import joblib
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.feature_extraction import DictVectorizer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
        from sklearn.model_selection import GroupShuffleSplit
        from sklearn.pipeline import Pipeline
    except ImportError as error:
        raise RuntimeError(
            "Model training requires the project dependencies; install requirements.txt"
        ) from error

    groups = np.asarray([record.session_id for record in records])
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_indices, test_indices = next(
        splitter.split(np.zeros(len(records)), [record.label for record in records], groups)
    )
    train_records = [records[index] for index in train_indices]
    test_records = [records[index] for index in test_indices]
    train_labels = [record.label for record in train_records]
    test_labels = [record.label for record in test_records]
    if len(set(train_labels)) < 2:
        raise ValueError(
            "The session-level training split contains fewer than two labels; "
            "collect more labeled sessions"
        )

    def make_pipeline(classifier: Any) -> Pipeline:
        return Pipeline(
            [
                ("vectorizer", DictVectorizer(sparse=False)),
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("classifier", classifier),
            ]
        )

    classifier_factories = {
        "logistic_regression": lambda: LogisticRegression(
            max_iter=1000, random_state=42, class_weight="balanced"
        ),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            class_weight="balanced",
        ),
    }

    inner_groups = np.asarray([record.session_id for record in train_records])
    inner_splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=43)
    inner_train_indices, validation_indices = next(
        inner_splitter.split(
            np.zeros(len(train_records)),
            train_labels,
            inner_groups,
        )
    )
    inner_train = [train_records[index] for index in inner_train_indices]
    validation = [train_records[index] for index in validation_indices]
    inner_train_labels = [record.label for record in inner_train]
    validation_labels = [record.label for record in validation]
    if len(set(inner_train_labels)) < 2:
        raise ValueError(
            "The grouped training split contains fewer than two labels; "
            "collect more labeled sessions"
        )

    inner_features = [_model_features(record.features) for record in inner_train]
    validation_features = [_model_features(record.features) for record in validation]
    training_features = [_model_features(record.features) for record in train_records]
    test_features = [_model_features(record.features) for record in test_records]
    all_labels = list(LABELS)
    evaluations: dict[str, dict[str, Any]] = {}
    validation_scores: dict[str, tuple[float, float]] = {}
    fitted_models: dict[str, Any] = {}
    for name, create_classifier in classifier_factories.items():
        validation_model = make_pipeline(create_classifier())
        validation_model.fit(inner_features, inner_train_labels)
        validation_predictions = validation_model.predict(validation_features).tolist()
        _, _, validation_f1, _ = precision_recall_fscore_support(
            validation_labels,
            validation_predictions,
            labels=all_labels,
            zero_division=0,
        )
        validation_scores[name] = (
            float(np.mean(validation_f1)),
            float(
                np.mean(
                    np.asarray(validation_labels) == np.asarray(validation_predictions)
                )
            ),
        )

        model = make_pipeline(create_classifier())
        model.fit(training_features, train_labels)
        predictions = model.predict(test_features).tolist()
        precision, recall, f1, _ = precision_recall_fscore_support(
            test_labels,
            predictions,
            labels=all_labels,
            zero_division=0,
        )
        evaluations[name] = {
            "accuracy": float(np.mean(np.asarray(test_labels) == np.asarray(predictions))),
            "macro_f1": float(np.mean(f1)),
            "per_class": {
                label: {
                    "precision": float(precision[index]),
                    "recall": float(recall[index]),
                    "f1": float(f1[index]),
                }
                for index, label in enumerate(all_labels)
            },
            "confusion_matrix": confusion_matrix(
                test_labels, predictions, labels=all_labels
            ).tolist(),
            "labels": all_labels,
            "validation_selection": {
                "macro_f1": validation_scores[name][0],
                "accuracy": validation_scores[name][1],
            },
            "held_out_sessions": sorted({record.session_id for record in test_records}),
        }
        fitted_models[name] = model

    rule_predictions = _rule_predictions(test_records)
    precision, recall, f1, _ = precision_recall_fscore_support(
        test_labels,
        rule_predictions,
        labels=all_labels,
        zero_division=0,
    )
    rules_evaluation = {
        "accuracy": float(np.mean(np.asarray(test_labels) == np.asarray(rule_predictions))),
        "macro_f1": float(np.mean(f1)),
        "per_class": {
            label: {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
            }
            for index, label in enumerate(all_labels)
        },
        "confusion_matrix": confusion_matrix(
            test_labels, rule_predictions, labels=all_labels
        ).tolist(),
        "labels": all_labels,
        "held_out_sessions": sorted({record.session_id for record in test_records}),
    }

    selected_name = max(
        classifier_factories,
        key=lambda name: (*validation_scores[name], name),
    )
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / f"{selected_name}.joblib"
    joblib.dump(fitted_models[selected_name], model_path)
    report = {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "split_strategy": "grouped_session_train_validation_test",
        "random_seeds": {"test_split": 42, "validation_split": 43},
        "train_rows": len(train_records),
        "validation_rows": len(validation),
        "test_rows": len(test_records),
        "candidate_models": evaluations,
        "rules_baseline": rules_evaluation,
        "selected_model": selected_name,
        "model_path": str(model_path.resolve()),
    }
    (destination / "evaluation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _model_features(features: FeatureVector) -> dict[str, Any]:
    return {
        field: (
            float("nan")
            if value is None and field != "active_app_category"
            else value
        )
        for field, value in features.items()
    }


def _rule_predictions(records: list[TrainingRecord]) -> list[str]:
    predictions: list[str] = []
    scorers: dict[str, AttentionScorer] = {}
    for record in records:
        features = record.features
        category = features["active_app_category"] or "unknown"
        scorer = scorers.setdefault(record.session_id, AttentionScorer())
        result = scorer.score(
            VisionSignals(
                face_present=(features["face_missing_ratio"] or 0.0) < 0.5,
                looking_at_screen=(features["gaze_away_ratio"] or 0.0) < 0.5,
                upright=(
                    None
                    if features["posture_score_mean"] is None
                    else features["posture_score_mean"] >= 0.5
                ),
                blink_rate=features["blink_rate_per_minute"] or 0.0,
            ),
            str(category),
        )
        predictions.append(result.state.value)
    return predictions


def run_training(
    csv_path: str | Path,
    output_dir: str | Path,
    database_path: str | Path,
) -> dict[str, Any]:
    records = read_training_csv(csv_path)
    report = train_and_evaluate(records, output_dir)
    version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    database = Database(database_path)
    try:
        database.register_model_version(
            name="focus_guard",
            version=version,
            metrics=report,
            file_path=report["model_path"],
            trained_at=datetime.now(timezone.utc).timestamp(),
        )
    finally:
        database.connection.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Focus Guard baseline classifiers")
    parser.add_argument("csv_path", type=Path, help="Labeled feature CSV from Focus Guard")
    parser.add_argument("--output-dir", type=Path, default=Path("models"))
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("focus_guard.db"),
        help="Database where the trained model version is recorded",
    )
    arguments = parser.parse_args()
    report = run_training(arguments.csv_path, arguments.output_dir, arguments.database)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
