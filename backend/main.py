from dataclasses import asdict
from time import time

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from backend.context.active_app import get_active_application
from backend.context.categories import categorize_application
from backend.core.alerts import AlertManager
from backend.core.scoring import AttentionScorer, VisionSignals
from backend.core.session import SessionManager
from backend.storage.database import Database


class UserCreateRequest(BaseModel):
    name: str
    email: str
    password: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


admin_security = HTTPBasic()


app = FastAPI(title="Focus Guard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
database = Database()
database.create_admin("admin", "admin123", "admin@focusguard.local")
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


@app.get("/users")
def get_users() -> list[dict[str, object]]:
    return database.list_users()


@app.post("/users")
def create_user(payload: UserCreateRequest) -> dict[str, object]:
    try:
        return database.create_user(payload.name, payload.email, payload.password)
    except Exception as error:  # pragma: no cover - defensive API guard
        raise HTTPException(400, str(error)) from error


@app.get("/admins")
def get_admins() -> list[dict[str, object]]:
    return database.list_admins()


@app.get("/admin/database/tables")
def database_tables(
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> list[dict[str, object]]:
    _require_admin(credentials)
    return database.list_tables()


@app.get("/admin/database/tables/{table_name}")
def database_table(
    table_name: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> dict[str, object]:
    _require_admin(credentials)
    try:
        return database.inspect_table(table_name, limit=limit, offset=offset)
    except ValueError as error:
        raise HTTPException(404, str(error)) from error


@app.post("/admin/login")
def admin_login(payload: AdminLoginRequest) -> dict[str, object]:
    if database.verify_admin(payload.username, payload.password):
        return {"ok": True, "username": payload.username}
    raise HTTPException(401, "Invalid admin credentials")


def _session_action(action, persist: bool = False) -> dict[str, object]:
    try:
        session = action()
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    if persist:
        database.save_session(session)
    return asdict(session) | {"state": session.state.value}


def _require_admin(credentials: HTTPBasicCredentials) -> None:
    if not database.verify_admin(credentials.username, credentials.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
