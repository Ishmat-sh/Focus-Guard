from dataclasses import asdict
import csv
from io import StringIO
import logging
import os
from pathlib import Path
from pickle import UnpicklingError
from threading import RLock
from time import monotonic, time
from typing import Any, Literal
from collections import deque

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from backend.context.active_app import get_active_application
from backend.context.categories import categorize_application
from backend.core.alerts import AlertManager
from backend.core.fatigue import FatigueEstimator, FatigueSnapshot
from backend.core.scoring import AttentionResult, AttentionScorer, AttentionState, VisionSignals
from backend.core.session import SessionManager
from backend.ml.inference import ModelInference
from backend.features.schema import FEATURE_FIELDS, FEATURE_SCHEMA_VERSION
from backend.features.windows import compute_window_features
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


class CollectionConsentRequest(BaseModel):
    consent: bool


class AttentionLabelRequest(BaseModel):
    start_elapsed_seconds: float = Field(ge=0)
    end_elapsed_seconds: float = Field(gt=0)
    label: Literal["focused", "drifting", "distracted", "fatigued"]


class RetentionRequest(BaseModel):
    retention_days: int | None = Field(default=None, ge=1, le=3650)


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
last_active_applications: dict[int, str] = {}
user_model_inferences: dict[int, ModelInference] = {}
user_model_errors: dict[int, str] = {}
user_frame_history: dict[int, tuple[int, deque[dict[str, Any]]]] = {}
user_fatigue_estimators: dict[int, FatigueEstimator] = {}
user_fatigue_snapshots: dict[int, FatigueSnapshot] = {}
runtime_lock = RLock()
scorer_mode = os.getenv("FOCUS_GUARD_SCORER", "rules").strip().lower()
if scorer_mode not in {"rules", "ml"}:
    raise RuntimeError("FOCUS_GUARD_SCORER must be either 'rules' or 'ml'")


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
            last_active_applications.pop(user_id, None)
            user_model_inferences.pop(user_id, None)
            user_model_errors.pop(user_id, None)
            user_frame_history.pop(user_id, None)
            user_fatigue_estimators.pop(user_id, None)
            user_fatigue_snapshots.pop(user_id, None)
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
    if database.collection_is_consented(int(result["id"]), user_id):
        _persist_feature_windows(int(result["id"]), user_id)
    database.apply_retention_policy(user_id)
    last_active_applications.pop(user_id, None)
    user_model_inferences.pop(user_id, None)
    user_model_errors.pop(user_id, None)
    user_frame_history.pop(user_id, None)
    user_fatigue_estimators.pop(user_id, None)
    user_fatigue_snapshots.pop(user_id, None)
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
    app_name = get_active_application()
    app_category = categorize_application(app_name).value
    result = user_scorer.score(signals, app_category, app_name)
    confidence: float | None = None
    inference_ms: float | None = None
    active_scorer = "rules"
    fallback_reason: str | None = None
    fatigue = _empty_fatigue_snapshot()
    with runtime_lock:
        session = _session_manager_for(user_id).snapshot()
        if session:
            if session.state.value == "running":
                fatigue = _fatigue_estimator_for(user_id).update(
                    snapshot.ear,
                    now=monotonic(),
                )
                user_fatigue_snapshots[user_id] = fatigue
            elif session.state.value == "paused":
                fatigue = user_fatigue_snapshots.get(user_id, fatigue)
            else:
                user_fatigue_estimators.pop(user_id, None)
                user_fatigue_snapshots.pop(user_id, None)
            previous_app = last_active_applications.get(user_id)
            app_switch_count = int(previous_app is not None and previous_app != app_name)
            last_active_applications[user_id] = app_name
            frame_sample = {
                "active_app_category": result.app_category,
                "app_switch_count": app_switch_count,
                "blink_rate_per_minute": snapshot.blink_rate,
                "ear": snapshot.ear,
                "face_present": snapshot.face_present,
                "gaze_offset_x": snapshot.gaze_offset_x,
                "gaze_offset_y": snapshot.gaze_offset_y,
                "head_pitch_degrees": snapshot.head_pitch_degrees,
                "head_roll_degrees": snapshot.head_roll_degrees,
                "head_yaw_degrees": snapshot.head_yaw_degrees,
                "looking_at_screen": snapshot.gaze == "looking_at_screen",
                "posture_score": snapshot.posture_score,
            }
            if session.state.value == "running":
                history = user_frame_history.get(user_id)
                if history is None or history[0] != session.id:
                    samples: deque[dict[str, Any]] = deque(maxlen=600)
                    user_frame_history[user_id] = (session.id, samples)
                else:
                    samples = history[1]
                samples.append(frame_sample | {"elapsed_seconds": session.elapsed_seconds})

                if scorer_mode == "ml":
                    result, confidence, inference_ms, fallback_reason = _score_with_model(
                        user_id,
                        session.id,
                        session.elapsed_seconds,
                        samples,
                        result,
                        app_category,
                        app_name,
                    )
                    if confidence is not None:
                        active_scorer = "ml"

            collecting = (
                session.state.value == "running"
                and database.collection_is_consented(session.id, user_id)
            )
            database.save_telemetry(
                session.id,
                time(),
                result,
                snapshot.face_present,
                elapsed_seconds=session.elapsed_seconds,
                features=frame_sample if collecting else None,
            )
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
        "scorer": active_scorer,
        "confidence": confidence,
        "inference_ms": inference_ms,
        "scorer_fallback_reason": fallback_reason,
        "fatigue_risk": fatigue.risk,
        "fatigue_level": fatigue.level,
        "perclos": fatigue.perclos,
        "average_blink_duration_seconds": fatigue.average_blink_duration_seconds,
        "slow_blink_count": fatigue.slow_blink_count,
        "break_suggestion": fatigue.break_suggestion,
        "fatigue_is_estimate": True,
    }


@app.post("/sessions/{session_id}/collection/consent")
def set_collection_consent(
    session_id: int,
    payload: CollectionConsentRequest,
    user: dict[str, object] = Depends(require_ready_user),
) -> dict[str, object]:
    user_id = int(user["id"])
    if not database.set_collection_consent(session_id, user_id, payload.consent):
        raise HTTPException(404, "Session not found")
    return {
        "session_id": session_id,
        "consent": payload.consent,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
    }


@app.post("/sessions/{session_id}/labels", status_code=201)
def create_session_label(
    session_id: int,
    payload: AttentionLabelRequest,
    user: dict[str, object] = Depends(require_ready_user),
) -> dict[str, object]:
    user_id = int(user["id"])
    session = database.session_for_user(session_id, user_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    if payload.start_elapsed_seconds >= payload.end_elapsed_seconds:
        raise HTTPException(422, "Label end time must be after its start time")
    current = _session_manager_for(user_id).snapshot()
    session_elapsed = (
        current.elapsed_seconds
        if current is not None and current.id == session_id
        else float(session["elapsed_seconds"])
    )
    if payload.end_elapsed_seconds > session_elapsed:
        raise HTTPException(422, "Label range cannot extend beyond the session")
    try:
        return database.create_label(
            session_id,
            user_id,
            payload.start_elapsed_seconds,
            payload.end_elapsed_seconds,
            payload.label,
        )
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get("/sessions/{session_id}/labels")
def list_session_labels(
    session_id: int,
    user: dict[str, object] = Depends(require_ready_user),
) -> list[dict[str, object]]:
    user_id = int(user["id"])
    if database.session_for_user(session_id, user_id) is None:
        raise HTTPException(404, "Session not found")
    try:
        return database.labels_for_session(session_id, user_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.get("/sessions/{session_id}/dataset.csv")
def export_session_dataset(
    session_id: int,
    user: dict[str, object] = Depends(require_ready_user),
) -> Response:
    user_id = int(user["id"])
    if database.session_for_user(session_id, user_id) is None:
        raise HTTPException(404, "Session not found")
    try:
        _persist_feature_windows(session_id, user_id)
        windows = database.labeled_feature_windows(session_id, user_id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error

    output = StringIO(newline="")
    columns = [
        "session_id",
        "window_start_seconds",
        "window_end_seconds",
        "label",
        "feature_schema_version",
        *FEATURE_FIELDS,
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for window in windows:
        writer.writerow(
            {
                "session_id": session_id,
                "window_start_seconds": window["start_elapsed_seconds"],
                "window_end_seconds": window["end_elapsed_seconds"],
                "label": window["label"],
                "feature_schema_version": window["schema_version"],
                **window["features"],
            }
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="focus-guard-session-{session_id}.csv"'
        },
    )


@app.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    user: dict[str, object] = Depends(require_ready_user),
) -> dict[str, bool]:
    user_id = int(user["id"])
    if not database.delete_session(session_id, user_id):
        raise HTTPException(404, "Session not found")
    _discard_session_runtime(user_id, session_id)
    return {"ok": True}


@app.get("/data/export.json")
def export_user_data(
    user: dict[str, object] = Depends(require_ready_user),
) -> Response:
    user_id = int(user["id"])
    exported = database.export_user_data(user_id)
    return JSONResponse(
        exported,
        headers={"Content-Disposition": 'attachment; filename="focus-guard-export.json"'},
    )


@app.delete("/data")
def delete_all_user_data(
    user: dict[str, object] = Depends(require_ready_user),
) -> dict[str, object]:
    user_id = int(user["id"])
    deleted_sessions = database.delete_all_user_data(user_id)
    _discard_session_runtime(user_id)
    return {"ok": True, "deleted_sessions": deleted_sessions}


@app.get("/privacy/retention")
def get_retention_policy(
    user: dict[str, object] = Depends(require_ready_user),
) -> dict[str, object]:
    return {"retention_days": database.retention_days(int(user["id"]))}


@app.put("/privacy/retention")
def set_retention_policy(
    payload: RetentionRequest,
    user: dict[str, object] = Depends(require_ready_user),
) -> dict[str, object]:
    user_id = int(user["id"])
    database.set_retention_days(user_id, payload.retention_days)
    deleted_telemetry = database.apply_retention_policy(user_id)
    return {
        "retention_days": payload.retention_days,
        "deleted_telemetry_rows": deleted_telemetry,
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
        last_active_applications.pop(user_id, None)
        user_model_inferences.pop(user_id, None)
        user_model_errors.pop(user_id, None)
        user_frame_history.pop(user_id, None)
        user_fatigue_estimators.pop(user_id, None)
        user_fatigue_snapshots.pop(user_id, None)
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


def _fatigue_estimator_for(user_id: int) -> FatigueEstimator:
    with runtime_lock:
        if user_id not in user_fatigue_estimators:
            user_fatigue_estimators[user_id] = FatigueEstimator()
        return user_fatigue_estimators[user_id]


def _empty_fatigue_snapshot() -> FatigueSnapshot:
    return FatigueSnapshot(0.0, "low", None, None, 0, False)


def _score_with_model(
    user_id: int,
    session_id: int,
    elapsed_seconds: float,
    samples: deque[dict[str, Any]],
    rules_result: AttentionResult,
    app_category: str,
    app_name: str,
) -> tuple[AttentionResult, float | None, float | None, str | None]:
    if user_id in user_model_errors:
        return rules_result, None, None, user_model_errors[user_id]
    window_start = max(0.0, elapsed_seconds - 10.0)
    window_samples = [
        sample
        for sample in samples
        if float(sample["elapsed_seconds"]) >= window_start
    ]
    if elapsed_seconds < 10.0 or not window_samples:
        return rules_result, None, None, "Waiting for a complete 10-second feature window"
    if float(window_samples[0]["elapsed_seconds"]) > window_start + 1.0:
        return rules_result, None, None, "Insufficient samples for a complete feature window"

    model = _model_inference_for(user_id)
    if model is None:
        return rules_result, None, None, user_model_errors.get(
            user_id, "No trained model is registered"
        )
    try:
        features = compute_window_features(
            window_samples,
            window_seconds=10.0,
            start_elapsed_seconds=window_start,
        )
        prediction = model.predict(features)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        logger.exception("ML attention inference failed; using the rules scorer")
        user_model_errors[user_id] = "ML inference failed; using the rules scorer"
        user_model_inferences.pop(user_id, None)
        return rules_result, None, None, user_model_errors[user_id]

    return (
        AttentionResult(
            score=prediction.score,
            state=prediction.state,
            raw_score=prediction.score,
            app_name=app_name,
            app_category=app_category,
        ),
        prediction.confidence,
        prediction.inference_ms,
        None,
    )


def _model_inference_for(user_id: int) -> ModelInference | None:
    if user_id in user_model_inferences:
        return user_model_inferences[user_id]
    if user_id in user_model_errors:
        return None

    configured_path = os.getenv("FOCUS_GUARD_MODEL_PATH")
    try:
        model_path = configured_path
        if not model_path:
            active_version = database.active_model_version("focus_guard")
            model_path = active_version["file_path"] if active_version else None
        if not model_path:
            raise FileNotFoundError("No trained model is registered")
        model = ModelInference(Path(model_path))
    except (AttributeError, EOFError, ImportError, OSError, UnpicklingError, ValueError) as error:
        logger.warning("ML model unavailable; using the rules scorer: %s", error)
        user_model_errors[user_id] = str(error)
        return None
    user_model_inferences[user_id] = model
    return model


def _alert_manager_for(user_id: int) -> AlertManager:
    with runtime_lock:
        if user_id not in user_alerts:
            user_alerts[user_id] = AlertManager()
        return user_alerts[user_id]


def _persist_feature_windows(session_id: int, user_id: int) -> None:
    if not database.collection_is_consented(session_id, user_id):
        return
    session = database.session_for_user(session_id, user_id)
    if session is None:
        return
    samples = database.feature_samples(session_id, user_id)
    if not samples:
        return
    current = _session_manager_for(user_id).snapshot()
    session_elapsed = (
        current.elapsed_seconds
        if current is not None and current.id == session_id
        else float(session["elapsed_seconds"])
    )
    grouped: dict[int, list[dict[str, object]]] = {}
    window_seconds = 10.0
    for sample in samples:
        bucket = int(float(sample["elapsed_seconds"]) // window_seconds)
        grouped.setdefault(bucket, []).append(sample)

    for bucket, frames in grouped.items():
        start = bucket * window_seconds
        last_sample = max(float(frame["elapsed_seconds"]) for frame in frames)
        end = min(start + window_seconds, max(last_sample, session_elapsed))
        if end <= start:
            continue
        features = compute_window_features(
            frames,
            end - start,
            start_elapsed_seconds=start,
        )
        database.save_feature_window(session_id, start, end, features)


def _discard_session_runtime(user_id: int, session_id: int | None = None) -> None:
    manager = session_managers.get(user_id)
    if session_id is not None and (
        manager is None or manager.current is None or manager.current.id != session_id
    ):
        return
    session_managers.pop(user_id, None)
    user_scorers.pop(user_id, None)
    user_alerts.pop(user_id, None)
    last_active_applications.pop(user_id, None)
    user_model_inferences.pop(user_id, None)
    user_model_errors.pop(user_id, None)
    user_frame_history.pop(user_id, None)
    user_fatigue_estimators.pop(user_id, None)
    user_fatigue_snapshots.pop(user_id, None)
    analyzer = user_face_analyzers.pop(user_id, None)
    if analyzer is not None:
        analyzer.close()


def _require_admin(credentials: HTTPBasicCredentials) -> None:
    if not database.verify_admin(credentials.username, credentials.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
