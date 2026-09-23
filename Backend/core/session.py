from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import monotonic
from typing import Callable


class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ENDED = "ended"
    COMPLETED = "completed"


@dataclass
class Session:
    id: int
    state: SessionState = SessionState.IDLE
    started_at: float | None = None
    ended_at: float | None = None
    elapsed_seconds: float = 0.0
    pause_started_at: float | None = None


class SessionManager:
    def __init__(self, clock: Callable[[], float] = monotonic, next_id: Callable[[], int] | None = None) -> None:
        self._clock = clock
        self._next_id_provider = next_id
        self._next_id = 1
        self.current: Session | None = None

    def start(self) -> Session:
        if self.current and self.current.state in {SessionState.RUNNING, SessionState.PAUSED}:
            raise ValueError("A session is already active")
        session_id = self._next_id_provider() if self._next_id_provider else self._next_id
        self.current = Session(session_id, SessionState.RUNNING, self._clock())
        self._next_id += 1
        return self.current

    def pause(self) -> Session:
        session = self._require_state(SessionState.RUNNING)
        self._refresh_elapsed(session)
        session.pause_started_at = self._clock()
        session.state = SessionState.PAUSED
        return session

    def resume(self) -> Session:
        session = self._require_state(SessionState.PAUSED)
        session.pause_started_at = None
        session.state = SessionState.RUNNING
        session.started_at = self._clock() - session.elapsed_seconds
        return session

    def end(self) -> Session:
        session = self._require_state(SessionState.RUNNING, SessionState.PAUSED)
        self._refresh_elapsed(session)
        session.ended_at = self._clock()
        session.state = SessionState.ENDED
        session.state = SessionState.COMPLETED
        return session

    def snapshot(self) -> Session | None:
        if self.current and self.current.state == SessionState.RUNNING:
            self._refresh_elapsed(self.current)
        return self.current

    def _refresh_elapsed(self, session: Session) -> None:
        if session.started_at is None:
            return
        if session.state == SessionState.PAUSED and session.pause_started_at is not None:
            session.elapsed_seconds = max(0.0, session.pause_started_at - session.started_at)
        elif session.state == SessionState.RUNNING:
            session.elapsed_seconds = max(0.0, self._clock() - session.started_at)

    def _require_state(self, *states: SessionState) -> Session:
        if not self.current or self.current.state not in states:
            expected = ", ".join(state.value for state in states)
            raise ValueError(f"Session must be {expected}")
        return self.current