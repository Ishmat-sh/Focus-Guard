from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isfinite
from time import monotonic


@dataclass(frozen=True)
class FatigueSnapshot:
    risk: float
    level: str
    perclos: float | None
    average_blink_duration_seconds: float | None
    slow_blink_count: int
    yawn_count: int
    break_suggestion: bool


class FatigueEstimator:
    def __init__(
        self,
        window_seconds: float = 600.0,
        slow_blink_seconds: float = 0.5,
        break_threshold: float = 70.0,
        sustained_seconds: float = 120.0,
        ear_threshold: float = 0.21,
        yawn_threshold: float = 0.6,
        yawn_duration_seconds: float = 1.0,
    ) -> None:
        if (
            not isfinite(window_seconds)
            or not isfinite(sustained_seconds)
            or not isfinite(slow_blink_seconds)
            or not isfinite(break_threshold)
            or not isfinite(ear_threshold)
            or not isfinite(yawn_threshold)
            or not isfinite(yawn_duration_seconds)
            or window_seconds <= 0
            or sustained_seconds <= 0
            or slow_blink_seconds <= 0
            or not 0 <= break_threshold <= 100
            or ear_threshold < 0
            or yawn_threshold <= 0
            or yawn_duration_seconds <= 0
        ):
            raise ValueError("Fatigue estimator durations must be greater than zero")
        self.window_seconds = window_seconds
        self.slow_blink_seconds = slow_blink_seconds
        self.break_threshold = break_threshold
        self.sustained_seconds = sustained_seconds
        self.ear_threshold = ear_threshold
        self.yawn_threshold = yawn_threshold
        self.yawn_duration_seconds = yawn_duration_seconds
        self._samples: deque[tuple[float, bool | None]] = deque()
        self._blink_durations: deque[tuple[float, float]] = deque()
        self._yawn_times: deque[float] = deque()
        self._eyes_closed_since: float | None = None
        self._mouth_open_since: float | None = None
        self._yawn_recorded_for_open = False
        self._last_sample_at: float | None = None
        self._high_risk_since: float | None = None

    def update(
        self,
        ear: float | None,
        mouth_aspect_ratio: float | None = None,
        now: float | None = None,
        active: bool = True,
    ) -> FatigueSnapshot:
        timestamp = monotonic() if now is None else now
        if not isfinite(timestamp):
            raise ValueError("now must be finite")
        if not active:
            self.reset()
            return self._snapshot(timestamp)
        if ear is not None and (not isfinite(ear) or ear < 0):
            raise ValueError("ear must be a non-negative finite value or null")
        if mouth_aspect_ratio is not None and (
            not isfinite(mouth_aspect_ratio) or mouth_aspect_ratio < 0
        ):
            raise ValueError(
                "mouth_aspect_ratio must be a non-negative finite value or null"
            )
        if self._last_sample_at is not None and timestamp < self._last_sample_at:
            raise ValueError("sample timestamps must be non-decreasing")

        eyes_closed = ear < self.ear_threshold if ear is not None else None
        if eyes_closed is True and self._eyes_closed_since is None:
            self._eyes_closed_since = timestamp
        elif eyes_closed is False and self._eyes_closed_since is not None:
            duration = timestamp - self._eyes_closed_since
            if 0 < duration <= 3.0:
                self._blink_durations.append((timestamp, duration))
            self._eyes_closed_since = None
        elif eyes_closed is None:
            self._eyes_closed_since = None

        if mouth_aspect_ratio is not None and mouth_aspect_ratio >= self.yawn_threshold:
            if self._mouth_open_since is None:
                self._mouth_open_since = timestamp
                self._yawn_recorded_for_open = False
            elif (
                not self._yawn_recorded_for_open
                and timestamp - self._mouth_open_since >= self.yawn_duration_seconds
            ):
                self._yawn_times.append(timestamp)
                self._yawn_recorded_for_open = True
        else:
            self._mouth_open_since = None
            self._yawn_recorded_for_open = False

        self._samples.append((timestamp, eyes_closed))
        self._last_sample_at = timestamp
        self._prune(timestamp)
        return self._snapshot(timestamp)

    def reset(self) -> None:
        self._samples.clear()
        self._blink_durations.clear()
        self._yawn_times.clear()
        self._eyes_closed_since = None
        self._mouth_open_since = None
        self._yawn_recorded_for_open = False
        self._last_sample_at = None
        self._high_risk_since = None

    def _snapshot(self, timestamp: float) -> FatigueSnapshot:
        observed_seconds = 0.0
        eyes_closed_seconds = 0.0
        perclos_samples: list[tuple[float, bool]] = []
        samples = list(self._samples)
        for index, (sample_time, closed) in enumerate(samples):
            if closed is None:
                continue
            next_time = (
                samples[index + 1][0]
                if index + 1 < len(samples)
                else timestamp
            )
            duration = min(max(0.0, next_time - sample_time), 5.0)
            observed_seconds += duration
            if closed:
                eyes_closed_seconds += duration
            perclos_samples.append((sample_time, closed))
        perclos = (
            eyes_closed_seconds / observed_seconds
            if observed_seconds > 0
            else None
        )
        blink_durations = [duration for _, duration in self._blink_durations]
        average_blink = (
            sum(blink_durations) / len(blink_durations)
            if blink_durations
            else None
        )
        slow_blinks = sum(
            duration >= self.slow_blink_seconds for duration in blink_durations
        )
        yawn_count = len(self._yawn_times)
        risk = min(
            100.0,
            (perclos or 0.0) * 150.0
            + min(40.0, slow_blinks / max(self.window_seconds / 60.0, 1.0) * 20.0)
            + min(20.0, yawn_count / max(self.window_seconds / 60.0, 1.0) * 10.0)
            + self._perclos_trend(perclos_samples),
        )
        if risk >= self.break_threshold:
            if self._high_risk_since is None:
                self._high_risk_since = timestamp
        else:
            self._high_risk_since = None
        break_suggestion = (
            self._high_risk_since is not None
            and timestamp - self._high_risk_since >= self.sustained_seconds
        )
        level = "high" if risk >= 65 else "moderate" if risk >= 35 else "low"
        return FatigueSnapshot(
            risk=risk,
            level=level,
            perclos=perclos,
            average_blink_duration_seconds=average_blink,
            slow_blink_count=slow_blinks,
            yawn_count=yawn_count,
            break_suggestion=break_suggestion,
        )

    def _perclos_trend(self, samples: list[tuple[float, bool]]) -> float:
        if len(samples) < 4:
            return 0.0
        midpoint = samples[0][0] + (samples[-1][0] - samples[0][0]) / 2.0
        earlier = [closed for timestamp, closed in samples if timestamp <= midpoint]
        later = [closed for timestamp, closed in samples if timestamp > midpoint]
        if not earlier or not later:
            return 0.0
        increase = sum(later) / len(later) - sum(earlier) / len(earlier)
        return min(10.0, max(0.0, increase * 25.0))

    def _prune(self, timestamp: float) -> None:
        cutoff = timestamp - self.window_seconds
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        while self._blink_durations and self._blink_durations[0][0] < cutoff:
            self._blink_durations.popleft()
        while self._yawn_times and self._yawn_times[0] < cutoff:
            self._yawn_times.popleft()
