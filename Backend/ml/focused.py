"""Train a participant-held-out one-class model from focused video recordings.

Run with: python -m backend.ml.focused Dataset
The model identifies samples that resemble the supplied focused recordings.
It cannot identify which non-focused state an outlier represents.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Any

from backend.features.schema import (
    FEATURE_SCHEMA_VERSION,
    FeatureVector,
    validate_feature_vector,
)
from backend.features.windows import compute_window_features

MODEL_NAME = "focus_guard_focused_baseline"
ARTIFACT_TYPE = "focus_guard_focused_baseline"
VISION_FEATURE_FIELDS = (
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
)
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}
IGNORED_DIRECTORY_NAMES = {".git", "venv", "node_modules"}


@dataclass(frozen=True)
class FocusedTrainingRecord:
    participant_id: str
    clip_id: str
    features: FeatureVector


@dataclass(frozen=True)
class FocusedBaselinePrediction:
    matches_focused_baseline: bool
    normality_score: float


class FocusedBaselineInference:
    def __init__(self, model_path: str | Path) -> None:
        import joblib

        artifact = joblib.load(model_path)
        if not isinstance(artifact, dict) or artifact.get("artifact_type") != ARTIFACT_TYPE:
            raise ValueError("The configured model is not a Focus Guard focused baseline")
        if artifact.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            raise ValueError("Focused baseline uses an incompatible feature schema")
        if tuple(artifact.get("feature_fields", ())) != VISION_FEATURE_FIELDS:
            raise ValueError("Focused baseline feature fields do not match this runtime")
        threshold = artifact.get("normality_threshold")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise ValueError("Focused baseline has an invalid normality threshold")
        if not math.isfinite(float(threshold)):
            raise ValueError("Focused baseline has an invalid normality threshold")
        self._artifact = artifact

    def predict(
        self, features: dict[str, object] | FeatureVector
    ) -> FocusedBaselinePrediction:
        import numpy as np

        vector = validate_feature_vector(dict(features))
        row = {
            field: (
                np.nan
                if vector[field] is None
                else float(vector[field])
            )
            for field in VISION_FEATURE_FIELDS
        }
        encoded = self._artifact["vectorizer"].transform([row])
        imputed = self._artifact["imputer"].transform(encoded)
        normality_score = float(self._artifact["detector"].score_samples(imputed)[0])
        threshold = float(self._artifact["normality_threshold"])
        return FocusedBaselinePrediction(
            matches_focused_baseline=normality_score >= threshold,
            normality_score=normality_score,
        )


def video_files(dataset_root: str | Path) -> list[Path]:
    root = Path(dataset_root)
    if not root.is_dir():
        raise ValueError(f"Dataset directory does not exist: {root}")
    paths: list[Path] = []
    for current, directories, filenames in os.walk(root):
        directories[:] = sorted(
            directory
            for directory in directories
            if directory.casefold() not in IGNORED_DIRECTORY_NAMES
            and not directory.casefold().startswith(".venv")
        )
        paths.extend(
            Path(current) / filename
            for filename in filenames
            if Path(filename).suffix.casefold() in VIDEO_EXTENSIONS
        )
    paths.sort()
    if not paths:
        raise ValueError(f"No supported video recordings were found in {root}")
    return paths


def extract_focused_records(
    dataset_root: str | Path,
    *,
    video_paths: list[Path] | None = None,
    sample_fps: float = 5.0,
    window_seconds: float = 10.0,
    minimum_face_coverage: float = 0.6,
) -> tuple[list[FocusedTrainingRecord], dict[str, int]]:
    if not math.isfinite(sample_fps) or sample_fps <= 0:
        raise ValueError("sample_fps must be finite and greater than zero")
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError("window_seconds must be finite and greater than zero")
    if not 0.0 < minimum_face_coverage <= 1.0:
        raise ValueError("minimum_face_coverage must be greater than 0 and at most 1")

    import cv2

    from backend.vision.analyzer import FaceAnalyzer

    root = Path(dataset_root)
    if video_paths is None:
        videos = video_files(root)
    else:
        videos = sorted(Path(path) for path in video_paths)
        for path in videos:
            if not path.is_file() or path.suffix.casefold() not in VIDEO_EXTENSIONS:
                raise ValueError(f"Invalid video recording path: {path}")
            try:
                path.relative_to(root)
            except ValueError as error:
                raise ValueError(f"Video recording is outside the dataset: {path}") from error
        if not videos:
            raise ValueError(f"No supported video recordings were provided for {root}")
    records: list[FocusedTrainingRecord] = []
    skipped_windows = 0
    rotated_videos = 0

    for video_number, path in enumerate(videos, start=1):
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(f"Could not open video recording: {path}")
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(source_fps) or source_fps <= 0:
            capture.release()
            raise RuntimeError(f"Video has an invalid frame rate: {path}")
        rotation = int(round(capture.get(cv2.CAP_PROP_ORIENTATION_META))) % 360
        if rotation not in {0, 90, 180, 270}:
            capture.release()
            raise RuntimeError(f"Video has an unsupported orientation: {path}")
        rotated_videos += int(rotation != 0)
        stride = max(1, round(source_fps / sample_fps))
        reported_frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        analyzer = FaceAnalyzer()
        frame_index = 0
        window_start = 0.0
        window_frames: list[dict[str, Any]] = []
        video_records = 0

        try:
            while capture.grab():
                if frame_index % stride == 0:
                    decoded, frame = capture.retrieve()
                    if not decoded or frame is None:
                        raise RuntimeError(
                            f"Could not decode a sampled frame from: {path}"
                        )
                    elapsed_seconds = frame_index / source_fps
                    while elapsed_seconds >= window_start + window_seconds:
                        if window_frames:
                            added, skipped = _append_window(
                                records,
                                window_frames,
                                path,
                                root,
                                window_start,
                                window_seconds,
                                minimum_face_coverage,
                            )
                            video_records += added
                            skipped_windows += skipped
                        window_frames = []
                        window_start += window_seconds

                    frame = _rotate_frame(frame, rotation, cv2)
                    height, width = frame.shape[:2]
                    scale = min(640.0 / max(height, width), 1.0)
                    if scale < 1.0:
                        frame = cv2.resize(
                            frame,
                            (round(width * scale), round(height * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                    snapshot = analyzer.process(frame, now=elapsed_seconds)
                    window_frames.append(
                        {
                            "active_app_category": "unknown",
                            "app_switch_count": 0.0,
                            "blink_rate_per_minute": snapshot.blink_rate,
                            "ear": snapshot.ear,
                            "elapsed_seconds": elapsed_seconds,
                            "face_present": snapshot.face_present,
                            "gaze_offset_x": snapshot.gaze_offset_x,
                            "gaze_offset_y": snapshot.gaze_offset_y,
                            "head_pitch_degrees": snapshot.head_pitch_degrees,
                            "head_roll_degrees": snapshot.head_roll_degrees,
                            "head_yaw_degrees": snapshot.head_yaw_degrees,
                            "looking_at_screen": snapshot.gaze == "looking_at_screen",
                            "posture_score": snapshot.posture_score,
                        }
                    )
                frame_index += 1

            video_duration = frame_index / source_fps
            if math.isfinite(reported_frame_count) and reported_frame_count > 0:
                video_duration = max(video_duration, reported_frame_count / source_fps)
            remaining_seconds = min(window_seconds, video_duration - window_start)
            if window_frames and remaining_seconds >= window_seconds / 2:
                added, skipped = _append_window(
                    records,
                    window_frames,
                    path,
                    root,
                    window_start,
                    remaining_seconds,
                    minimum_face_coverage,
                )
                video_records += added
                skipped_windows += skipped
        finally:
            capture.release()
            analyzer.close()

        print(
            f"Processed recording {video_number}/{len(videos)}; "
            f"accepted windows so far: {len(records)}"
        )
        if video_records == 0:
            print("This recording contributed no windows meeting the face-coverage threshold.")

    if not records:
        raise ValueError(
            "No training windows met the minimum face-coverage requirement"
        )
    return records, {
        "videos_found": len(videos),
        "videos_processed": len(videos),
        "videos_rotation_corrected": rotated_videos,
        "windows_extracted": len(records),
        "windows_skipped_low_face_coverage": skipped_windows,
    }


def _rotate_frame(frame: Any, rotation: int, cv2_module: Any) -> Any:
    if rotation == 90:
        return cv2_module.rotate(frame, cv2_module.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2_module.rotate(frame, cv2_module.ROTATE_180)
    if rotation == 270:
        return cv2_module.rotate(frame, cv2_module.ROTATE_90_COUNTERCLOCKWISE)
    return frame


def _append_window(
    records: list[FocusedTrainingRecord],
    frames: list[dict[str, Any]],
    video_path: Path,
    dataset_root: Path,
    start_seconds: float,
    duration_seconds: float,
    minimum_face_coverage: float,
) -> tuple[int, int]:
    feature_vector = compute_window_features(
        frames,
        window_seconds=duration_seconds,
        start_elapsed_seconds=start_seconds,
    )
    coverage = 1.0 - float(feature_vector["face_missing_ratio"] or 0.0)
    if coverage < minimum_face_coverage:
        return 0, 1
    participant_id = video_path.parent.name
    if not participant_id:
        raise ValueError(f"Could not determine participant directory for {video_path}")
    records.append(
        FocusedTrainingRecord(
            participant_id=participant_id,
            clip_id=video_path.relative_to(dataset_root).as_posix(),
            features=feature_vector,
        )
    )
    return 1, 0


def train_focused_baseline(
    records: list[FocusedTrainingRecord],
    output_dir: str | Path,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
) -> dict[str, Any]:
    if not 0.0 < contamination < 0.5:
        raise ValueError("contamination must be greater than 0 and less than 0.5")
    participants = {record.participant_id for record in records}
    if len(participants) < 5:
        raise ValueError(
            "At least five distinct participants are required for held-out evaluation"
        )
    if len(records) < 2:
        raise ValueError("At least two focused feature windows are required")

    import joblib
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import GroupShuffleSplit

    rows = [_model_features(record.features) for record in records]
    groups = np.asarray([record.participant_id for record in records])
    train_indices, test_indices = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state).split(
            np.zeros(len(records)), groups=groups
        )
    )
    train_rows = [rows[index] for index in train_indices]
    test_rows = [rows[index] for index in test_indices]

    validation_vectorizer = DictVectorizer(sparse=False)
    validation_train = validation_vectorizer.fit_transform(train_rows)
    validation_imputer = SimpleImputer(strategy="median", add_indicator=True)
    validation_train = validation_imputer.fit_transform(validation_train)
    validation_detector = IsolationForest(
        n_estimators=300,
        contamination="auto",
        random_state=random_state,
        n_jobs=-1,
    )
    validation_detector.fit(validation_train)
    train_scores = validation_detector.score_samples(validation_train)
    validation_threshold = float(np.quantile(train_scores, contamination))
    test_matrix = validation_imputer.transform(
        validation_vectorizer.transform(test_rows)
    )
    test_scores = validation_detector.score_samples(test_matrix)
    heldout_acceptance = float(np.mean(test_scores >= validation_threshold))

    vectorizer = DictVectorizer(sparse=False)
    encoded = vectorizer.fit_transform(rows)
    imputer = SimpleImputer(strategy="median", add_indicator=True)
    imputed = imputer.fit_transform(encoded)
    detector = IsolationForest(
        n_estimators=300,
        contamination="auto",
        random_state=random_state,
        n_jobs=-1,
    )
    detector.fit(imputed)
    all_scores = detector.score_samples(imputed)
    normality_threshold = float(np.quantile(all_scores, contamination))

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "focused_isolation_forest.joblib"
    artifact = {
        "artifact_type": ARTIFACT_TYPE,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_fields": list(VISION_FEATURE_FIELDS),
        "vectorizer": vectorizer,
        "imputer": imputer,
        "detector": detector,
        "normality_threshold": normality_threshold,
    }
    joblib.dump(artifact, model_path)

    test_participants = {
        records[index].participant_id for index in test_indices
    }
    train_participants = {
        records[index].participant_id for index in train_indices
    }
    report = {
        "model_type": "one_class_focused_baseline",
        "training_target": "focused_only",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_fields": list(VISION_FEATURE_FIELDS),
        "split_strategy": "participant_grouped_holdout",
        "random_state": random_state,
        "contamination_threshold": contamination,
        "training_windows": len(records),
        "training_participants": len(participants),
        "heldout_windows": len(test_indices),
        "heldout_participants": len(test_participants),
        "heldout_focused_acceptance_rate": heldout_acceptance,
        "heldout_focused_rejection_rate": 1.0 - heldout_acceptance,
        "participant_splits_disjoint": not bool(
            test_participants & train_participants
        ),
        "nonfocused_examples": 0,
        "nonfocused_detection_metrics": None,
        "model_path": str(model_path.resolve()),
    }
    (destination / "focused_evaluation.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def _model_features(features: FeatureVector) -> dict[str, float]:
    validated = validate_feature_vector(dict(features))
    return {
        field: (
            float("nan")
            if validated[field] is None
            else float(validated[field])
        )
        for field in VISION_FEATURE_FIELDS
    }


def run_training(
    dataset_root: str | Path,
    output_dir: str | Path,
    database_path: str | Path,
    *,
    sample_fps: float = 5.0,
    window_seconds: float = 10.0,
    minimum_face_coverage: float = 0.6,
    contamination: float = 0.05,
) -> dict[str, Any]:
    records, extraction = extract_focused_records(
        dataset_root,
        sample_fps=sample_fps,
        window_seconds=window_seconds,
        minimum_face_coverage=minimum_face_coverage,
    )
    report = train_focused_baseline(
        records,
        output_dir,
        contamination=contamination,
    )
    report["extraction"] = extraction
    report["sample_fps"] = sample_fps
    report["window_seconds"] = window_seconds
    report["minimum_face_coverage"] = minimum_face_coverage
    report["trained_at"] = datetime.now(timezone.utc).isoformat()
    report["model_version"] = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = Path(output_dir)
    (destination / "focused_evaluation.json").write_text(
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
        description="Train a focused-only novelty detector from video recordings"
    )
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("models/focused_baseline"))
    parser.add_argument("--database", type=Path, default=Path("focus_guard.db"))
    parser.add_argument("--sample-fps", type=float, default=5.0)
    parser.add_argument("--window-seconds", type=float, default=10.0)
    parser.add_argument("--minimum-face-coverage", type=float, default=0.6)
    parser.add_argument("--contamination", type=float, default=0.05)
    arguments = parser.parse_args()
    report = run_training(
        arguments.dataset_root,
        arguments.output_dir,
        arguments.database,
        sample_fps=arguments.sample_fps,
        window_seconds=arguments.window_seconds,
        minimum_face_coverage=arguments.minimum_face_coverage,
        contamination=arguments.contamination,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
