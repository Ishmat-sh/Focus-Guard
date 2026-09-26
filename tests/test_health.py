from fastapi.testclient import TestClient
import cv2
import numpy as np
import pytest
from uuid import uuid4

import backend.main as main
from backend.storage.database import Database
from backend.vision.analyzer import VisionSnapshot

app = main.app


@pytest.fixture(autouse=True)
def isolate_api_database(tmp_path, monkeypatch):
    test_database = Database(tmp_path / "api.db")
    monkeypatch.setattr(main, "database", test_database)
    monkeypatch.setattr(main, "session_managers", {})
    monkeypatch.setattr(main, "user_scorers", {})
    monkeypatch.setattr(main, "user_face_analyzers", {})
    monkeypatch.setattr(main, "user_alerts", {})
    yield test_database
    test_database.connection.close()


def register_user(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/users",
        json={"name": "Test User", "email": email, "password": "safe-pass-123"},
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


def test_cors_allows_frontend_from_lan_ip() -> None:
    response = TestClient(app).options(
        "/admin/login",
        headers={
            "Origin": "http://192.168.1.45:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://192.168.1.45:5173"


def test_database_explorer_endpoints_are_read_only_and_paginated(isolate_api_database) -> None:
    client = TestClient(app)
    username = f"test-admin-{uuid4().hex}"
    password = "test-admin-password"
    isolate_api_database.create_admin(username, password)

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


def test_admin_users_endpoint_returns_all_safe_user_details(isolate_api_database) -> None:
    client = TestClient(app)
    username = f"users-admin-{uuid4().hex}"
    password = "users-admin-password"
    email = f"admin-list-{uuid4().hex}@example.com"
    isolate_api_database.create_admin(username, password)
    created = isolate_api_database.create_user("Admin List User", email, "user-password-123")

    assert client.get("/users").status_code == 401
    response = client.get("/users", auth=(username, password))

    assert response.status_code == 200
    user = next(item for item in response.json() if item["id"] == created["id"])
    assert user["name"] == "Admin List User"
    assert user["email"] == email
    assert "created_at" in user
    assert user["password"] == "[redacted]"


def test_focus_status_endpoint() -> None:
    client = TestClient(app)
    headers = register_user(client, f"focus-{uuid4().hex}@example.com")
    response = client.get("/focus-status", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "idle"
    assert response.json()["session_length_minutes"] == 25


def test_session_lifecycle_and_attention_endpoints() -> None:
    client = TestClient(app)
    headers = register_user(client, f"lifecycle-{uuid4().hex}@example.com")
    start = client.post("/sessions/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["state"] == "running"
    assert client.post("/sessions/pause", headers=headers).json()["state"] == "paused"
    assert client.post("/sessions/resume", headers=headers).json()["state"] == "running"
    assert client.post("/sessions/end", headers=headers).json()["state"] == "completed"
    assert client.get("/history", headers=headers).status_code == 200


def test_focus_data_requires_auth_and_isolated_by_user() -> None:
    client = TestClient(app)
    first_headers = register_user(client, f"first-{uuid4().hex}@example.com")
    second_headers = register_user(client, f"second-{uuid4().hex}@example.com")

    assert client.get("/sessions/current").status_code == 401
    assert client.post("/sessions/start").status_code == 401
    first_start = client.post("/sessions/start", headers=first_headers)
    assert first_start.status_code == 200
    assert client.get("/sessions/current", headers=second_headers).json()["state"] == "idle"
    assert client.post("/sessions/end", headers=first_headers).status_code == 200

    first_history = client.get("/history", headers=first_headers).json()
    second_history = client.get("/history", headers=second_headers).json()
    assert first_history[0]["user_id"] is not None
    assert first_history[0]["id"] == first_start.json()["id"]
    assert second_history == []


def test_attention_frame_endpoint_uses_analyzed_camera_signals(monkeypatch) -> None:
    class FakeAnalyzer:
        def process(self, frame):
            return VisionSnapshot(
                face_present=True,
                blink_count=2,
                blink_rate=0.5,
                head_pose="forward",
                gaze="looking_at_screen",
                posture="upright",
            )

    monkeypatch.setattr("backend.main._face_analyzer_for", lambda user_id: FakeAnalyzer())
    client = TestClient(app)
    headers = register_user(client, f"vision-{uuid4().hex}@example.com")
    success, encoded = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    assert success

    response = client.post(
        "/attention/frame",
        content=encoded.tobytes(),
        headers={**headers, "Content-Type": "image/jpeg"},
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
    assert registered.json()["access_token"]
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
    assert login.json()["access_token"]

    token_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/sessions/current", headers=token_headers).status_code == 200
    assert client.post("/auth/logout", headers=token_headers).status_code == 204
    assert client.get("/sessions/current", headers=token_headers).status_code == 401


def test_admin_reset_issues_temporary_password_that_must_be_changed(isolate_api_database) -> None:
    client = TestClient(app)
    email = f"password-reset-{uuid4().hex}@example.com"
    user = isolate_api_database.create_user("Reset User", email, "original-password")
    stale_token = isolate_api_database.issue_user_token(user["id"])
    admin_name = f"reset-admin-{uuid4().hex}"
    admin_password = "reset-admin-password"
    isolate_api_database.create_admin(admin_name, admin_password)
    route = f"/admin/users/{user['id']}/password-reset"

    assert client.post(route).status_code == 401
    reset = client.post(route, auth=(admin_name, admin_password))
    assert reset.status_code == 200
    temporary_password = reset.json()["temporary_password"]
    assert isolate_api_database.get_user_for_token(stale_token) is None
    assert client.post(
        "/auth/login", json={"email": email, "password": "original-password"}
    ).status_code == 401

    temporary_login = client.post(
        "/auth/login", json={"email": email, "password": temporary_password}
    )
    assert temporary_login.status_code == 200
    assert temporary_login.json()["user"]["must_change_password"] is True
    temporary_headers = {"Authorization": f"Bearer {temporary_login.json()['access_token']}"}
    assert client.get("/sessions/current", headers=temporary_headers).status_code == 403

    changed = client.post(
        "/auth/change-password",
        headers=temporary_headers,
        json={"new_password": "replacement-password"},
    )
    assert changed.status_code == 200
    assert changed.json()["user"]["must_change_password"] is False
    assert client.post(
        "/auth/login", json={"email": email, "password": temporary_password}
    ).status_code == 401
    assert client.post(
        "/auth/login", json={"email": email, "password": "replacement-password"}
    ).status_code == 200


def test_admin_can_delete_user(isolate_api_database) -> None:
    client = TestClient(app)
    user = isolate_api_database.create_user(
        "Remove User", f"remove-{uuid4().hex}@example.com", "safe-password"
    )
    token = isolate_api_database.issue_user_token(user["id"])
    admin_name = f"delete-admin-{uuid4().hex}"
    admin_password = "delete-admin-password"
    isolate_api_database.create_admin(admin_name, admin_password)
    route = f"/admin/users/{user['id']}"

    assert client.delete(route).status_code == 401
    deleted = client.delete(route, auth=(admin_name, admin_password))
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert isolate_api_database.get_user_for_token(token) is None
    assert all(row["id"] != user["id"] for row in isolate_api_database.list_users())
    assert client.delete(route, auth=(admin_name, admin_password)).status_code == 404