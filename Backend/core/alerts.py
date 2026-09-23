from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class Alert:
    kind: str
    message: str
    created_at: float


class AlertManager:
    def __init__(self, threshold_seconds: float = 12.0, cooldown_seconds: float = 60.0) -> None:
        self.threshold_seconds = threshold_seconds
        self.cooldown_seconds = cooldown_seconds
        self._distracted_since: float | None = None
        self._last_alert_at: float | None = None

    def update(self, is_distracted: bool, active: bool, now: float | None = None) -> Alert | None:
        current = monotonic() if now is None else now
        if not active:
            self.reset()
            return None
        if not is_distracted:
            self._distracted_since = None
            return None
        if self._distracted_since is None:
            self._distracted_since = current
            return None
        sustained = current - self._distracted_since >= self.threshold_seconds
        cooled_down = self._last_alert_at is None or current - self._last_alert_at >= self.cooldown_seconds
        if sustained and cooled_down:
            self._last_alert_at = current
            return Alert("distraction", "You have been distracted for a while.", current)
        return None

    def reset(self) -> None:
        self._distracted_since = None
        self._last_alert_at = None