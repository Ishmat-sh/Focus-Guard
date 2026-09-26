from dataclasses import asdict
import os
from time import time

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

from Backend.context.active_app import get_active_application
from Backend.context.categories import categorize_application
from Backend.core.alerts import AlertManager
from Backend.core.scoring import AttentionScorer, VisionSignals
from Backend.core.session import SessionManager
from Backend.storage.database import Database
from Backend.vision.analyzer import FaceAnalyzer


class UserCreateRequest(BaseModel):
    name: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
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
bootstrap_admin_username = os.getenv("FOCUS_GUARD_ADMIN_USERNAME")
bootstrap_admin_password = os.getenv("FOCUS_GUARD_ADMIN_PASSWORD")
if bootstrap_admin_username and bootstrap_admin_password:
    database.create_admin(bootstrap_admin_username, bootstrap_admin_password)
session_manager = SessionManager(next_id=database.next_session_id)
scorer = AttentionScorer()
alerts = AlertManager()
face_analyzer = FaceAnalyzer()


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


@app.post("/attention/frame")
def analyze_attention_frame(frame: bytes = Body(..., media_type="image/jpeg")) -> dict[str, object]:
    if not frame:
        raise HTTPException(400, "An image frame is required")
    if len(frame) > 2_000_000:
        raise HTTPException(413, "Image frame must be 2 MB or smaller")

    import cv2
    import numpy as np

    image = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode image frame")

    snapshot = face_analyzer.process(image)
    app_name = get_active_application()
    category = categorize_application(app_name)
    signals = VisionSignals(
        face_present=snapshot.face_present,
        looking_at_screen=snapshot.gaze == "looking_at_screen",
        upright=snapshot.posture == "upright",
        blink_rate=snapshot.blink_rate,
    )
    result = scorer.score(signals, category.value, app_name)
    session = session_manager.snapshot()
    if session:
        database.save_telemetry(session.id, time(), result, snapshot.face_present)
    alert = alerts.update(
        result.state.value == "distracted",
        bool(session and session.state.value == "running"),
    )
    vision_score = max(
        0,
        100
        - (0 if snapshot.face_present else 50)
        - (0 if snapshot.gaze == "looking_at_screen" else 30)
        - (0 if snapshot.posture == "upright" else 20),
    )
    return asdict(result) | {
        "state": result.state.value,
        "face_present": snapshot.face_present,
        "blink_count": snapshot.blink_count,
        "blink_frequency": snapshot.blink_rate,
        "gaze": snapshot.gaze,
        "head_pose": snapshot.head_pose,
        "posture": snapshot.posture,
        "vision_score": vision_score,
        "alert": asdict(alert) if alert else None,
    }


@app.get("/metrics")
def metrics() -> dict[str, object]:
    session = session_manager.snapshot()
    return {"session": asdict(session) | {"state": session.state.value} if session else None, "history": database.history()}


@app.get("/history")
def history() -> list[dict[str, object]]:
    return database.history()


@app.post("/users", status_code=201)
def create_user(payload: UserCreateRequest) -> dict[str, object]:
    if len(payload.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    try:
        return database.create_user(payload.name, payload.email, payload.password)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.post("/auth/login")
def user_login(payload: UserLoginRequest) -> dict[str, object]:
    user = database.verify_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "Invalid email or password")
    return {"ok": True, "user": user}


@app.post("/admin/login")
def admin_login(payload: AdminLoginRequest) -> dict[str, object]:
    if not database.verify_admin(payload.username, payload.password):
        raise HTTPException(401, "Invalid admin credentials")
    return {"ok": True, "username": payload.username}


@app.get("/users")
def list_users(
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> list[dict[str, object]]:
    _require_admin(credentials)
    return database.list_users()


@app.get("/admins")
def list_admins(
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> list[dict[str, object]]:
    _require_admin(credentials)
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
