from dataclasses import asdict
import os
from threading import RLock
from time import time

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from pydantic import BaseModel

from backend.core.alerts import AlertManager
from backend.core.scoring import AttentionScorer, VisionSignals
from backend.core.session import SessionManager
from backend.storage.database import Database
from backend.vision.analyzer import FaceAnalyzer


class UserCreateRequest(BaseModel):
    name: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserPasswordChangeRequest(BaseModel):
    new_password: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


admin_security = HTTPBasic()
user_security = HTTPBearer(auto_error=False)

app = FastAPI(title="Focus Guard API")
configured_origins = [
    origin.strip()
    for origin in os.getenv("FOCUS_GUARD_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *configured_origins],
    allow_origin_regex=r"^http://(?:localhost|127\.0\.0\.1|(?:\d{1,3}\.){3}\d{1,3}):5173$",
    allow_methods=["*"],
    allow_headers=["*"],
)
database = Database(os.getenv("FOCUS_GUARD_DB_PATH") or "focus_guard.db")
bootstrap_admin_username = os.getenv("FOCUS_GUARD_ADMIN_USERNAME")
bootstrap_admin_password = os.getenv("FOCUS_GUARD_ADMIN_PASSWORD")
if bootstrap_admin_username and bootstrap_admin_password:
    database.create_admin(bootstrap_admin_username, bootstrap_admin_password)
session_managers: dict[int, SessionManager] = {}
user_scorers: dict[int, AttentionScorer] = {}
user_face_analyzers: dict[int, FaceAnalyzer] = {}
user_alerts: dict[int, AlertManager] = {}
runtime_lock = RLock()


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(user_security),
) -> dict[str, object]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate": "Bearer"})
    user = database.get_user_for_token(credentials.credentials)
    if user is None:
        raise HTTPException(401, "Session expired; please sign in again", headers={"WWW-Authenticate": "Bearer"})
    return user | {"_token": credentials.credentials}


def require_ready_user(user: dict[str, object] = Depends(require_user)) -> dict[str, object]:
    if user["must_change_password"]:
        raise HTTPException(403, "Change your temporary password before continuing")
    return user


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Focus Guard API is running", "docs": "/docs"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/focus-status")
def focus_status(user: dict[str, object] = Depends(require_ready_user)) -> dict[str, object]:
    session = _session_manager_for(int(user["id"])).snapshot()
    return {
        "status": session.state.value if session else "idle",
        "session_length_minutes": 25,
        "break_length_minutes": 5,
        "is_active": bool(session and session.state.value in {"running", "paused"}),
        "message": "Ready to focus",
    }


@app.post("/sessions/start")
def start_session(user: dict[str, object] = Depends(require_ready_user)) -> dict[str, object]:
    user_id = int(user["id"])
    try:
        with runtime_lock:
            session = _session_manager_for(user_id).start()
            database.save_session(session, user_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return asdict(session) | {"state": session.state.value}


@app.post("/sessions/pause")
def pause_session(user: dict[str, object] = Depends(require_ready_user)) -> dict[str, object]:
    user_id = int(user["id"])
    return _session_action(_session_manager_for(user_id).pause, user_id)


@app.post("/sessions/resume")
def resume_session(user: dict[str, object] = Depends(require_ready_user)) -> dict[str, object]:
    user_id = int(user["id"])
    return _session_action(_session_manager_for(user_id).resume, user_id)


@app.post("/sessions/end")
def end_session(user: dict[str, object] = Depends(require_ready_user)) -> dict[str, object]:
    user_id = int(user["id"])
    result = _session_action(_session_manager_for(user_id).end, user_id)
    _alert_manager_for(user_id).reset()
    return result


@app.get("/sessions/current")
def current_session(user: dict[str, object] = Depends(require_ready_user)) -> dict[str, object]:
    session = _session_manager_for(int(user["id"])).snapshot()
    return asdict(session) | {"state": session.state.value} if session else {"state": "idle"}


@app.post("/attention/frame")
def analyze_attention_frame(
    frame: bytes = Body(..., media_type="image/jpeg"),
    user: dict[str, object] = Depends(require_ready_user),
) -> dict[str, object]:
    if not frame:
        raise HTTPException(400, "An image frame is required")
    if len(frame) > 2_000_000:
        raise HTTPException(413, "Image frame must be 2 MB or smaller")

    import cv2
    import numpy as np

    image = cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "Could not decode image frame")

    user_id = int(user["id"])
    analyzer = _face_analyzer_for(user_id)
    user_scorer = _scorer_for(user_id)
    snapshot = analyzer.process(image)
    signals = VisionSignals(
        face_present=snapshot.face_present,
        looking_at_screen=snapshot.gaze == "looking_at_screen",
        upright=None if snapshot.posture == "unknown" else snapshot.posture == "upright",
        blink_rate=snapshot.blink_rate,
    )
    app_name = "Unknown"
    result = user_scorer.score(signals, "unknown", app_name)
    with runtime_lock:
        session = _session_manager_for(user_id).snapshot()
        if session:
            database.save_telemetry(session.id, time(), result, snapshot.face_present)
    alert = _alert_manager_for(user_id).update(
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
        "blink_rate_per_minute": snapshot.blink_rate,
        "gaze": snapshot.gaze,
        "head_pose": snapshot.head_pose,
        "posture": snapshot.posture,
        "vision_score": vision_score,
        "alert": asdict(alert) if alert else None,
    }


@app.get("/metrics")
def metrics(user: dict[str, object] = Depends(require_ready_user)) -> dict[str, object]:
    user_id = int(user["id"])
    session = _session_manager_for(user_id).snapshot()
    return {
        "session": asdict(session) | {"state": session.state.value} if session else None,
        "history": database.user_history(user_id),
    }


@app.get("/history")
def history(user: dict[str, object] = Depends(require_ready_user)) -> list[dict[str, object]]:
    return database.user_history(int(user["id"]))


@app.post("/users", status_code=201)
def create_user(payload: UserCreateRequest) -> dict[str, object]:
    if len(payload.password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    try:
        user = database.create_user(payload.name, payload.email, payload.password)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return {"user": user, "access_token": database.issue_user_token(int(user["id"]))}


@app.post("/auth/login")
def user_login(payload: UserLoginRequest) -> dict[str, object]:
    user = database.verify_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "Invalid email or password")
    return {"ok": True, "user": user, "access_token": database.issue_user_token(int(user["id"]))}


@app.post("/auth/change-password")
def change_password(
    payload: UserPasswordChangeRequest,
    user: dict[str, object] = Depends(require_user),
) -> dict[str, object]:
    if not user["must_change_password"]:
        raise HTTPException(409, "Password change is not currently required")
    if len(payload.new_password) < 8:
        raise HTTPException(422, "Password must be at least 8 characters")
    updated_user = database.change_user_password(int(user["id"]), payload.new_password)
    if updated_user is None:
        raise HTTPException(404, "User account no longer exists")
    return {
        "ok": True,
        "user": updated_user,
        "access_token": database.issue_user_token(int(user["id"])),
    }


@app.post("/auth/logout", status_code=204)
def user_logout(user: dict[str, object] = Depends(require_user)) -> None:
    database.revoke_user_token(str(user["_token"]))


@app.post("/admin/login")
def admin_login(payload: AdminLoginRequest) -> dict[str, object]:
    if not database.verify_admin(payload.username, payload.password):
        raise HTTPException(401, "Invalid admin credentials")
    return {"ok": True, "username": payload.username}


@app.post("/admin/users/{user_id}/password-reset")
def reset_user_password(
    user_id: int,
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> dict[str, str]:
    _require_admin(credentials)
    temporary_password = database.reset_user_password(user_id)
    if temporary_password is None:
        raise HTTPException(404, "User not found")
    return {"temporary_password": temporary_password}


@app.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> dict[str, bool]:
    _require_admin(credentials)
    with runtime_lock:
        if not database.delete_user(user_id):
            raise HTTPException(404, "User not found")
        session_managers.pop(user_id, None)
        user_scorers.pop(user_id, None)
        user_alerts.pop(user_id, None)
        analyzer = user_face_analyzers.pop(user_id, None)
    if analyzer is not None:
        analyzer.close()
    return {"ok": True}


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


def _session_action(action, user_id: int) -> dict[str, object]:
    try:
        with runtime_lock:
            session = action()
            database.save_session(session, user_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    return asdict(session) | {"state": session.state.value}


def _session_manager_for(user_id: int) -> SessionManager:
    with runtime_lock:
        if user_id not in session_managers:
            session_managers[user_id] = SessionManager(next_id=database.next_session_id)
        return session_managers[user_id]


def _scorer_for(user_id: int) -> AttentionScorer:
    with runtime_lock:
        if user_id not in user_scorers:
            user_scorers[user_id] = AttentionScorer()
        return user_scorers[user_id]


def _face_analyzer_for(user_id: int) -> FaceAnalyzer:
    with runtime_lock:
        if user_id not in user_face_analyzers:
            user_face_analyzers[user_id] = FaceAnalyzer()
        return user_face_analyzers[user_id]


def _alert_manager_for(user_id: int) -> AlertManager:
    with runtime_lock:
        if user_id not in user_alerts:
            user_alerts[user_id] = AlertManager()
        return user_alerts[user_id]


def _require_admin(credentials: HTTPBasicCredentials) -> None:
    if not database.verify_admin(credentials.username, credentials.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
