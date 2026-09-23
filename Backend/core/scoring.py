from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum


class AttentionState(str, Enum):
    FOCUSED = "focused"
    DRIFTING = "drifting"
    DISTRACTED = "distracted"
    FATIGUED = "fatigued"


@dataclass
class VisionSignals:
    face_present: bool = False
    looking_at_screen: bool = False
    upright: bool = True
    blink_rate: float = 0.0


@dataclass
class AttentionResult:
    score: float
    state: AttentionState
    raw_score: float
    app_name: str
    app_category: str


class AttentionScorer:
    def __init__(self, window_size: int = 8) -> None:
        self._scores: deque[float] = deque(maxlen=window_size)
        self._fatigue_samples = 0

    def score(self, vision: VisionSignals, app_category: str, app_name: str = "Unknown") -> AttentionResult:
        raw = 100.0
        if not vision.face_present:
            raw -= 45
        if not vision.looking_at_screen:
            raw -= 30
        if not vision.upright:
            raw -= 15
        if app_category == "distracting":
            raw -= 35
        elif app_category == "neutral":
            raw -= 5
        elif app_category == "unknown":
            raw -= 10
        if vision.blink_rate > 30:
            self._fatigue_samples += 1
            raw -= 8
        else:
            self._fatigue_samples = max(0, self._fatigue_samples - 1)
        raw = max(0.0, min(100.0, raw))
        self._scores.append(raw)
        average = sum(self._scores) / len(self._scores)
        return AttentionResult(average, self._state(average), raw, app_name, app_category)

    def _state(self, score: float) -> AttentionState:
        if self._fatigue_samples >= 4:
            return AttentionState.FATIGUED
        if score >= 75:
            return AttentionState.FOCUSED
        if score >= 50:
            return AttentionState.DRIFTING
        return AttentionState.DISTRACTED