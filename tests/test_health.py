from fastapi.testclient import TestClient
import cv2
import numpy as np
from uuid import uuid4

from backend.main import app, database
from backend.vision.analyzer import VisionSnapshot


def test_root_endpoint() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Focus Guard API is running",
        "docs": "/docs",
    }


def test_health_check() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_explorer_endpoints_are_read_only_and_paginated() -> None:
    client = TestClient(app)
    username = f"test-admin-{uuid4().hex}"
    password = "test-admin-password"
    database.create_admin(username, password)

    assert client.get("/admin/database/tables").status_code == 401

    tables_response = client.get("/admin/database/tables", auth=(username, password))
    assert tables_response.status_code == 200
    assert {table["name"] for table in tables_response.json()} >= {
        "sessions",
        "telemetry",
        "users",
        "admins",
    }

    table_response = client.get(
        "/admin/database/tables/users?limit=1&offset=0",
        auth=(username, password),
    )
    assert table_response.status_code == 200
    assert table_response.json()["name"] == "users"
    assert "columns" in table_response.json()
    assert len(table_response.json()["rows"]) <= 1
    assert client.get(
        "/admin/database/tables/not_a_table",
        auth=(username, password),
    ).status_code == 404


def test_admin_users_endpoint_returns_all_safe_user_details() -> None:
    client = TestClient(app)
    username = f"users-admin-{uuid4().hex}"
    password = "users-admin-password"
    email = f"admin-list-{uuid4().hex}@example.com"
    database.create_admin(username, password)
    created = database.create_user("Admin List User", email, "user-password-123")

    assert client.get("/users").status_code == 401
    response = client.get("/users", auth=(username, password))

    assert response.status_code == 200
    user = next(item for item in response.json() if item["id"] == created["id"])
    assert user["name"] == "Admin List User"
    assert user["email"] == email
    assert "created_at" in user
    assert user["password"] == "[redacted]"


def test_focus_status_endpoint() -> None:
    response = TestClient(app).get("/focus-status")

    assert response.status_code == 200
    assert response.json()["status"] == "idle"
    assert response.json()["session_length_minutes"] == 25


def test_session_lifecycle_and_attention_endpoints() -> None:
    client = TestClient(app)
    start = client.post("/sessions/start")
    assert start.status_code == 200
    assert start.json()["state"] == "running"
    assert client.get("/attention").status_code == 200
    assert client.post("/sessions/pause").json()["state"] == "paused"
    assert client.post("/sessions/resume").json()["state"] == "running"
    assert client.post("/sessions/end").json()["state"] == "completed"
    assert client.get("/history").status_code == 200


def test_attention_frame_endpoint_uses_analyzed_camera_signals(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.main.face_analyzer.process",
        lambda frame: VisionSnapshot(
            face_present=True,
            blink_count=2,
            blink_rate=0.5,
            head_pose="forward",
            gaze="looking_at_screen",
            posture="upright",
        ),
    )
    success, encoded = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    assert success

    response = TestClient(app).post(
        "/attention/frame",
        content=encoded.tobytes(),
        headers={"Content-Type": "image/jpeg"},
    )

    assert response.status_code == 200
    assert response.json()["face_present"] is True
    assert response.json()["gaze"] == "looking_at_screen"
    assert response.json()["posture"] == "upright"
    assert response.json()["vision_score"] == 100


def test_user_registration_and_login_endpoints() -> None:
    client = TestClient(app)
    email = f"auth-{uuid4().hex}@example.com"
    registered = client.post(
        "/users",
        json={"name": "Auth Flow", "email": email, "password": "safe-pass-123"},
    )

    assert registered.status_code == 201
    assert "password" not in registered.json()
    assert client.post(
        "/users",
        json={"name": "Duplicate", "email": email.upper(), "password": "safe-pass-123"},
    ).status_code == 409
    assert client.post(
        "/auth/login", json={"email": email, "password": "wrong-password"}
    ).status_code == 401
    login = client.post(
        "/auth/login", json={"email": email.upper(), "password": "safe-pass-123"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email