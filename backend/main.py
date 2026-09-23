from dataclasses import asdict
from time import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.context.active_app import get_active_application
from backend.context.categories import categorize_application
from backend.core.alerts import AlertManager
from backend.core.scoring import AttentionScorer, VisionSignals
from backend.core.session import SessionManager
from backend.storage.database import Database


app = FastAPI(title="Focus Guard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
database = Database()
session_manager = SessionManager(next_id=database.next_session_id)
scorer = AttentionScorer()
alerts = AlertManager()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Focus Guard API is running", "docs": "/docs"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/focus-status")
def focus_status() -> dict[str, object]:
    session = session_manager.snapshot()
    return {
        "status": session.state.value if session else "idle",
        "session_length_minutes": 25,
        "break_length_minutes": 5,
        "is_active": bool(session and session.state.value in {"running", "paused"}),
        "message": "Ready to focus",
    }


@app.post("/sessions/start")
def start_session() -> dict[str, object]:
    try:
        session = session_manager.start()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    database.save_session(session)
    return asdict(session) | {"state": session.state.value}


@app.post("/sessions/pause")
def pause_session() -> dict[str, object]:
    return _session_action(session_manager.pause, persist=True)


@app.post("/sessions/resume")
def resume_session() -> dict[str, object]:
    return _session_action(session_manager.resume, persist=True)


@app.post("/sessions/end")
def end_session() -> dict[str, object]:
    result = _session_action(session_manager.end, persist=True)
    alerts.reset()
    return result


@app.get("/sessions/current")
def current_session() -> dict[str, object]:
    session = session_manager.snapshot()
    return asdict(session) | {"state": session.state.value} if session else {"state": "idle"}


@app.get("/attention")
def attention() -> dict[str, object]:
    app_name = get_active_application()
    category = categorize_application(app_name)
    result = scorer.score(VisionSignals(), category.value, app_name)
    session = session_manager.snapshot()
    if session:
        database.save_telemetry(session.id, time(), result, False)
    alert = alerts.update(result.state.value == "distracted", bool(session and session.state.value == "running"))
    return asdict(result) | {"state": result.state.value, "alert": asdict(alert) if alert else None}


@app.get("/metrics")
def metrics() -> dict[str, object]:
    session = session_manager.snapshot()
    return {"session": asdict(session) | {"state": session.state.value} if session else None, "history": database.history()}


@app.get("/history")
def history() -> list[dict[str, object]]:
    return database.history()


def _session_action(action, persist: bool = False) -> dict[str, object]:
    try:
        session = action()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    if persist:
        database.save_session(session)
    return asdict(session) | {"state": session.state.value}
