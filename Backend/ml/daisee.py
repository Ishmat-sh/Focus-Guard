"""Train an engagement-level classifier from the locally supplied DAiSEE data."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

from backend.features.schema import (
    FEATURE_SCHEMA_VERSION,
    FeatureVector,
    validate_feature_vector,
)
from backend.ml.focused import (
    VISION_FEATURE_FIELDS,
    extract_focused_records,
    video_files,
)

MODEL_NAME = "focus_guard_daisee_engagement"
ARTIFACT_TYPE = "focus_guard_daisee_engagement"
SPLITS = ("Train", "Validation", "Test")
ENGAGEMENT_LEVELS = (0, 1, 2, 3)


@dataclass(frozen=True)
class DaiseeEngagementRecord:
    participant_id: str
    clip_id: str
    engagement_level: int
    features: FeatureVector


class DaiseeEngagementInference:
    def __init__(self, model_path: str | Path) -> None:
        import joblib

        artifact = joblib.load(model_path)
        if not isinstance(artifact, dict) or artifact.get("artifact_type") != ARTIFACT_TYPE:
            raise ValueError("The configured model is not a DAiSEE engagement classifier")
        if artifact.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            raise ValueError("DAiSEE engagement model uses an incompatible feature schema")
        if tuple(artifact.get("feature_fields", ())) != VISION_FEATURE_FIELDS:
            raise ValueError("DAiSEE engagement feature fields do not match this runtime")
        pipeline = artifact.get("pipeline")
        if not callable(getattr(pipeline, "predict", None)):
            raise ValueError("DAiSEE engagement model has no prediction pipeline")
        self._pipeline = pipeline

    def predict(self, features: dict[str, object] | FeatureVector) -> int:
        vector = validate_feature_vector(dict(features))
        row = {
            field: math.nan if vector[field] is None else float(vector[field])
            for field in VISION_FEATURE_FIELDS
        }
        return int(self._pipeline.predict([row])[0])


def load_split_labels(dataset_root: str | Path, split: str) -> dict[str, int]:
    if split not in SPLITS:
        raise ValueError(f"Unsupported DAiSEE split: {split}")
    root = Path(dataset_root)
    labels_path = root / "Labels" / f"{split}Labels.csv"
    manifest_path = root / "DataSet" / f"{split}.txt"
    if not labels_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(f"Missing DAiSEE labels or manifest for {split}")

    manifest = {
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    }
    labels: dict[str, int] = {}
    with labels_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"DAiSEE {split} labels are missing a header row")
        field_names = {name.strip(): name for name in reader.fieldnames}
        if not {"ClipID", "Engagement"}.issubset(field_names):
            raise ValueError(f"DAiSEE {split} labels need ClipID and Engagement columns")
        for line_number, row in enumerate(reader, start=2):
            clip_id = (row[field_names["ClipID"]] or "").strip()
            raw_level = (row[field_names["Engagement"]] or "").strip()
            if not clip_id:
                raise ValueError(f"DAiSEE {split} row {line_number} has no ClipID")
            if clip_id not in manifest:
                raise ValueError(
                    f"DAiSEE {split} label {clip_id} is absent from its official manifest"
                )
            try:
                level = int(raw_level)
            except ValueError as error:
                raise ValueError(
                    f"DAiSEE {split} row {line_number} has an invalid engagement level"
                ) from error
            if level not in ENGAGEMENT_LEVELS:
                raise ValueError(
                    f"DAiSEE {split} row {line_number} has an unsupported engagement level"
                )
            if clip_id in labels:
                raise ValueError(f"DAiSEE {split} has duplicate label {clip_id}")
            labels[clip_id] = level
    if not labels:
        raise ValueError(f"DAiSEE {split} labels contain no clips")
    return labels


def _records_for_split(
    dataset_root: Path,
    split: str,
    labels: dict[str, int],
    *,
    sample_fps: float,
    window_seconds: float,
    minimum_face_coverage: float,
) -> tuple[list[DaiseeEngagementRecord], dict[str, int]]:
    split_root = dataset_root / "DataSet" / split
    videos = video_files(split_root)
    by_name: dict[str, Path] = {}
    for path in videos:
        if path.name in by_name:
            raise ValueError(f"Duplicate DAiSEE clip filename in {split}: {path.name}")
        by_name[path.name] = path
    labeled_videos = [by_name[clip_id] for clip_id in labels if clip_id in by_name]
    feature_records, extraction = extract_focused_records(
        split_root,
        video_paths=labeled_videos,
        sample_fps=sample_fps,
        window_seconds=window_seconds,
        minimum_face_coverage=minimum_face_coverage,
    )
    records: list[DaiseeEngagementRecord] = []
    clips_with_features: set[str] = set()
    for record in feature_records:
        parts = Path(record.clip_id).parts
        if len(parts) < 3:
            raise ValueError(f"Unexpected DAiSEE video layout: {record.clip_id}")
        clip_id = parts[-1]
        level = labels.get(clip_id)
        if level is None:
            continue
        records.append(
            DaiseeEngagementRecord(
                participant_id=parts[0],
                clip_id=record.clip_id,
                engagement_level=level,
                features=record.features,
            )
        )
        clips_with_features.add(clip_id)
    if not records:
        raise ValueError(f"No labeled DAiSEE {split} windows met face-coverage requirements")

    extraction.update(
        {
            "labeled_clips": len(labels),
            "labeled_clips_missing_video": len(set(labels) - by_name.keys()),
            "unlabeled_videos": len(set(by_name) - labels.keys()),
            "labeled_clips_with_features": len(clips_with_features),
            "labeled_clips_without_features": (
                len(labels) - len(set(labels) - by_name.keys()) - len(clips_with_features)
            ),
            "labeled_windows_extracted": len(records),
        }
    )
    return records, extraction


def _model_features(features: FeatureVector) -> dict[str, float]:
    validated = validate_feature_vector(dict(features))
    return {
        field: (
            math.nan
            if validated[field] is None
            else float(validated[field])
        )
        for field in VISION_FEATURE_FIELDS
    }


def _evaluation(
    labels: list[int],
    predictions: list[int],
) -> dict[str, Any]:
    import numpy as np
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        precision_recall_fscore_support,
    )

    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        predictions,
        labels=ENGAGEMENT_LEVELS,
        zero_division=0,
    )
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(np.mean(f1)),
        "per_level": {
            str(level): {
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
            }
            for index, level in enumerate(ENGAGEMENT_LEVELS)
        },
        "confusion_matrix": confusion_matrix(
            labels,
            predictions,
            labels=ENGAGEMENT_LEVELS,
        ).tolist(),
    }


def train_daisee_engagement_model(
    train_records: list[DaiseeEngagementRecord],
    validation_records: list[DaiseeEngagementRecord],
    test_records: list[DaiseeEngagementRecord],
    output_dir: str | Path,
) -> dict[str, Any]:
    if not train_records or not validation_records or not test_records:
        raise ValueError("DAiSEE train, validation, and test splits must all be non-empty")
    split_participants = [
        {record.participant_id for record in records}
        for records in (train_records, validation_records, test_records)
    ]
    if any(
        split_participants[left] & split_participants[right]
        for left, right in ((0, 1), (0, 2), (1, 2))
    ):
        raise ValueError("DAiSEE participants overlap between official splits")
    if set(record.engagement_level for record in train_records) != set(ENGAGEMENT_LEVELS):
        raise ValueError("DAiSEE training split must contain engagement levels 0, 1, 2, and 3")

    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    def make_pipeline(classifier: Any) -> Pipeline:
        return Pipeline(
            [
                ("vectorizer", DictVectorizer(sparse=False)),
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("classifier", classifier),
            ]
        )

    factories = {
        "logistic_regression": lambda: LogisticRegression(
            class_weight="balanced",
            max_iter=2000,
            random_state=42,
        ),
        "random_forest": lambda: RandomForestClassifier(
            class_weight="balanced_subsample",
            n_estimators=300,
            n_jobs=-1,
            random_state=42,
        ),
    }
    train_x = [_model_features(record.features) for record in train_records]
    validation_x = [_model_features(record.features) for record in validation_records]
    test_x = [_model_features(record.features) for record in test_records]
    train_y = [record.engagement_level for record in train_records]
    validation_y = [record.engagement_level for record in validation_records]
    test_y = [record.engagement_level for record in test_records]

    validation_scores: dict[str, dict[str, float]] = {}
    best_name: str | None = None
    best_key = (-1.0, -1.0)
    for name, create_classifier in factories.items():
        candidate = make_pipeline(create_classifier())
        candidate.fit(train_x, train_y)
        evaluation = _evaluation(validation_y, candidate.predict(validation_x).tolist())
        score = {
            "accuracy": evaluation["accuracy"],
            "macro_f1": evaluation["macro_f1"],
        }
        validation_scores[name] = score
        key = (score["macro_f1"], score["accuracy"])
        if key > best_key:
            best_name = name
            best_key = key
    if best_name is None:
        raise RuntimeError("Could not select a DAiSEE engagement classifier")

    final_pipeline = make_pipeline(factories[best_name]())
    combined_records = train_records + validation_records
    final_x = train_x + validation_x
    final_y = train_y + validation_y
    final_pipeline.fit(final_x, final_y)
    test_evaluation = _evaluation(test_y, final_pipeline.predict(test_x).tolist())

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "daisee_engagement.joblib"
    trained_at = datetime.now(timezone.utc)
    model_version = trained_at.strftime("%Y%m%dT%H%M%SZ")
    joblib.dump(
        {
            "artifact_type": ARTIFACT_TYPE,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "feature_fields": list(VISION_FEATURE_FIELDS),
            "model_version": model_version,
            "pipeline": final_pipeline,
        },
        model_path,
    )

    report = {
        "model_type": "daisee_engagement_level_classifier",
        "training_target": "DAiSEE Engagement label, unchanged (0-3)",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_fields": list(VISION_FEATURE_FIELDS),
        "labels": list(ENGAGEMENT_LEVELS),
        "split_strategy": "official_participant_disjoint_train_validation_test",
        "participant_splits_disjoint": True,
        "training_windows": len(train_records),
        "validation_windows": len(validation_records),
        "test_windows": len(test_records),
        "training_participants": len(split_participants[0]),
        "validation_participants": len(split_participants[1]),
        "test_participants": len(split_participants[2]),
        "training_level_counts": {
            str(level): train_y.count(level) for level in ENGAGEMENT_LEVELS
        },
        "validation_level_counts": {
            str(level): validation_y.count(level) for level in ENGAGEMENT_LEVELS
        },
        "test_level_counts": {
            str(level): test_y.count(level) for level in ENGAGEMENT_LEVELS
        },
        "validation_model_scores": validation_scores,
        "selected_model": best_name,
        "test_evaluation": test_evaluation,
        "model_path": str(model_path.resolve()),
        "model_version": model_version,
        "trained_at": trained_at.isoformat(),
    }
    (destination / "daisee_evaluation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def run_training(
    dataset_root: str | Path,
    output_dir: str | Path,
    database_path: str | Path,
    *,
    sample_fps: float = 5.0,
    window_seconds: float = 10.0,
    minimum_face_coverage: float = 0.6,
) -> dict[str, Any]:
    root = Path(dataset_root)
    if not root.is_dir():
        raise ValueError(f"DAiSEE dataset directory does not exist: {root}")
    if not math.isfinite(sample_fps) or sample_fps <= 0:
        raise ValueError("sample_fps must be finite and greater than zero")
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError("window_seconds must be finite and greater than zero")
    if not 0.0 < minimum_face_coverage <= 1.0:
        raise ValueError("minimum_face_coverage must be greater than 0 and at most 1")

    labels = {split: load_split_labels(root, split) for split in SPLITS}
    participant_sets: dict[str, set[str]] = {}
    for split in SPLITS:
        split_root = root / "DataSet" / split
        participant_sets[split] = {
            path.relative_to(split_root).parts[0]
            for path in video_files(split_root)
            if len(path.relative_to(split_root).parts) >= 3
        }
    for index, first in enumerate(SPLITS):
        for second in SPLITS[index + 1 :]:
            if participant_sets[first] & participant_sets[second]:
                raise ValueError(
                    f"DAiSEE participants overlap between {first} and {second}"
                )

    records: dict[str, list[DaiseeEngagementRecord]] = {}
    extraction: dict[str, dict[str, int]] = {}
    for split in SPLITS:
        records[split], extraction[split] = _records_for_split(
            root,
            split,
            labels[split],
            sample_fps=sample_fps,
            window_seconds=window_seconds,
            minimum_face_coverage=minimum_face_coverage,
        )
    report = train_daisee_engagement_model(
        records["Train"],
        records["Validation"],
        records["Test"],
        output_dir,
    )
    report["extraction"] = extraction
    report["sample_fps"] = sample_fps
    report["window_seconds"] = window_seconds
    report["minimum_face_coverage"] = minimum_face_coverage
    destination = Path(output_dir)
    (destination / "daisee_evaluation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    from backend.storage.database import Database

    database = Database(database_path)
    try:
        database.register_model_version(
            name=MODEL_NAME,
            version=report["model_version"],
            metrics=report,
            file_path=report["model_path"],
            trained_at=datetime.now(timezone.utc).timestamp(),
        )
    finally:
        database.connection.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a DAiSEE engagement-level classifier from local videos"
    )
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/daisee_engagement"),
    )
    parser.add_argument("--database", type=Path, default=Path("focus_guard.db"))
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--window-seconds", type=float, default=10.0)
    parser.add_argument("--minimum-face-coverage", type=float, default=0.6)
    arguments = parser.parse_args()
    report = run_training(
        arguments.dataset_root,
        arguments.output_dir,
        arguments.database,
        sample_fps=arguments.sample_fps,
        window_seconds=arguments.window_seconds,
        minimum_face_coverage=arguments.minimum_face_coverage,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
