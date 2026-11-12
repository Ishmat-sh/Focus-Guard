from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from logging import getLogger
from math import isclose, isfinite
from pathlib import Path
from time import perf_counter
from typing import Any

from backend.core.scoring import AttentionState
from backend.features.schema import FeatureVector, validate_feature_vector

logger = getLogger(__name__)
STATE_SCORES = {
    AttentionState.FOCUSED.value: 100.0,
    AttentionState.DRIFTING.value: 65.0,
    AttentionState.DISTRACTED.value: 25.0,
    AttentionState.FATIGUED.value: 35.0,
}


@dataclass(frozen=True)
class ModelPrediction:
    score: float
    state: AttentionState
    confidence: float
    inference_ms: float


class ModelInference:
    def __init__(self, model_path: str | Path, smoothing_windows: int = 8) -> None:
        if smoothing_windows < 1:
            raise ValueError("smoothing_windows must be at least one")
        import joblib

        self.model = joblib.load(model_path)
        if not hasattr(self.model, "predict_proba") or not hasattr(self.model, "classes_"):
            raise ValueError("The configured model must support predict_proba and classes_")
        self._scores: deque[float] = deque(maxlen=smoothing_windows)

    def predict(self, features: dict[str, object] | FeatureVector) -> ModelPrediction:
        vector = validate_feature_vector(dict(features))
        model_features = [
            {
                name: (
                    float("nan")
                    if value is None and name != "active_app_category"
                    else value
                )
                for name, value in vector.items()
            }
        ]
        started = perf_counter()
        probabilities = [float(value) for value in self.model.predict_proba(model_features)[0]]
        inference_ms = (perf_counter() - started) * 1000.0
        classes = [str(label) for label in self.model.classes_]
        if len(classes) != len(probabilities):
            raise ValueError("Model class labels do not match its probability output")
        if any(label not in STATE_SCORES for label in classes):
            raise ValueError("Model contains an unsupported attention class")
        if (
            not all(isfinite(value) and 0.0 <= value <= 1.0 for value in probabilities)
            or not isclose(sum(probabilities), 1.0, abs_tol=1e-6)
        ):
            raise ValueError("Model returned invalid class probabilities")
        confidence_index = max(range(len(classes)), key=lambda index: probabilities[index])
        confidence = probabilities[confidence_index]
        predicted_state = AttentionState(classes[confidence_index])
        raw_score = sum(
            probabilities[index] * STATE_SCORES[label]
            for index, label in enumerate(classes)
        )
        self._scores.append(raw_score)
        score = sum(self._scores) / len(self._scores)
        if predicted_state == AttentionState.FATIGUED:
            state = AttentionState.FATIGUED
        elif score >= 75:
            state = AttentionState.FOCUSED
        elif score >= 50:
            state = AttentionState.DRIFTING
        else:
            state = AttentionState.DISTRACTED
        logger.info("ML attention inference completed in %.2f ms", inference_ms)
        return ModelPrediction(score, state, confidence, inference_ms)
