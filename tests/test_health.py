import json
from fastapi.testclient import TestClient
import cv2
import numpy as np
import pytest
from uuid import uuid4
from time import sleep, time

import backend.main as main
from backend.core.scoring import AttentionResult, AttentionState
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
    monkeypatch.setattr(main, "last_active_applications", {})
    monkeypatch.setattr(main, "user_model_inferences", {})
    monkeypatch.setattr(main, "user_model_errors", {})
    monkeypatch.setattr(main, "user_focused_baselines", {})
    monkeypatch.setattr(main, "user_focused_baseline_errors", {})
    monkeypatch.setattr(main, "user_frame_history", {})
    monkeypatch.setattr(main, "user_fatigue_estimators", {})
    monkeypatch.setattr(main, "user_fatigue_snapshots", {})
    monkeypatch.setattr(main, "user_scorer_modes", {})
    monkeypatch.setattr(main, "lighting_adapters", {})
    monkeypatch.setattr(main, "scorer_mode", "rules")
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


def test_session_timeline_is_authenticated_and_scoped_to_owner(isolate_api_database) -> None:
    client = TestClient(app)
    owner_headers = register_user(client, f"timeline-owner-{uuid4().hex}@example.com")
    other_headers = register_user(client, f"timeline-other-{uuid4().hex}@example.com")
    session_response = client.post("/sessions/start", headers=owner_headers)
    session_id = session_response.json()["id"]
    recorded_at = time()
    result = AttentionResult(88.0, AttentionState.FOCUSED, 88.0, "Editor", "productive")
    isolate_api_database.save_telemetry(
        session_id,
        recorded_at,
        result,
        True,
        elapsed_seconds=1.0,
    )
    isolate_api_database.save_browser_context(
        session_id,
        "github.com",
        recorded_at - 1,
        0.0,
    )

    assert client.get(f"/sessions/{session_id}/timeline").status_code == 401
    owner_response = client.get(
        f"/sessions/{session_id}/timeline",
        headers=owner_headers,
    )
    assert owner_response.status_code == 200
    assert owner_response.json()[0]["domain"] == "github.com"
    domain_usage = client.get("/analytics/domains", headers=owner_headers)
    assert domain_usage.status_code == 200
    assert domain_usage.json()[0]["domain"] == "github.com"
    assert client.get(
        f"/sessions/{session_id}/timeline",
        headers=other_headers,
    ).status_code == 404


def test_admin_telemetry_reports_live_users_and_can_end_a_session(isolate_api_database) -> None:
    client = TestClient(app)
    username = f"telemetry-admin-{uuid4().hex}"
    password = "admin-password-123"
    isolate_api_database.create_admin(username, password)
    headers = register_user(client, f"telemetry-user-{uuid4().hex}@example.com")
    session_response = client.post("/sessions/start", headers=headers)
    assert session_response.status_code == 200

    assert client.get("/admin/telemetry").status_code == 401
    assert client.post("/admin/users/1/sessions/end").status_code == 401
    telemetry = client.get("/admin/telemetry", auth=(username, password))
    assert telemetry.status_code == 200
    user = telemetry.json()["users"][0]
    assert telemetry.json()["summary"]["active_sessions"] == 1
    assert user["current_session"]["state"] == "running"

    ended = client.post(
        f"/admin/users/{user['id']}/sessions/end",
        auth=(username, password),
    )
    assert ended.status_code == 200
    assert ended.json()["state"] == "completed"


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


def test_session_lifecycle_and_attention_endpoints(isolate_api_database) -> None:
    client = TestClient(app)
    headers = register_user(client, f"lifecycle-{uuid4().hex}@example.com")
    start = client.post("/sessions/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["state"] == "running"
    assert client.post("/sessions/pause", headers=headers).json()["state"] == "paused"
    assert client.post("/sessions/resume", headers=headers).json()["state"] == "running"
    ended = client.post("/sessions/end", headers=headers)
    assert ended.json()["state"] == "completed"
    assert ended.json()["summary"]["observed_seconds"] == 0
    persisted = isolate_api_database.connection.execute(
        "SELECT session_id, focus_percentage, distraction_percentage "
        "FROM session_summaries WHERE session_id = ?",
        (start.json()["id"],),
    ).fetchone()
    assert persisted["session_id"] == start.json()["id"]
    assert persisted["focus_percentage"] == 0
    assert persisted["distraction_percentage"] == 0
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
    monkeypatch.setattr("backend.main.get_active_application", lambda: "YouTube")
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
    assert response.json()["app_category"] == "distracting"
    assert response.json()["scorer"] == "rules"
    assert response.json()["confidence"] is None
    assert response.json()["focus_baseline_status"] == "unavailable"
    assert response.json()["focus_baseline_normality_score"] is None


def test_scorer_status_and_per_user_toggle(isolate_api_database) -> None:
    client = TestClient(app)
    headers = register_user(client, f"scorer-{uuid4().hex}@example.com")

    initial = client.get("/scorer", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["configured_mode"] == "rules"
    assert initial.json()["effective_mode"] == "rules"

    changed = client.put("/scorer", headers=headers, json={"mode": "ml"})
    assert changed.status_code == 200
    assert changed.json()["configured_mode"] == "ml"
    assert changed.json()["effective_mode"] == "rules"
    assert changed.json()["fallback_reason"]

    restored = client.put("/scorer", headers=headers, json={"mode": "rules"})
    assert restored.status_code == 200
    assert restored.json()["effective_mode"] == "rules"


def test_consent_gated_labels_and_dataset_export(monkeypatch, isolate_api_database) -> None:
    class FakeAnalyzer:
        def process(self, frame):
            return VisionSnapshot(
                face_present=True,
                blink_count=1,
                blink_rate=1.0,
                ear=0.3,
                head_pose="forward",
                head_yaw_degrees=2.0,
                head_pitch_degrees=1.0,
                head_roll_degrees=0.0,
                gaze="looking_at_screen",
                gaze_offset_x=0.01,
                gaze_offset_y=0.02,
            )

    monkeypatch.setattr("backend.main._face_analyzer_for", lambda user_id: FakeAnalyzer())
    monkeypatch.setattr("backend.main.get_active_application", lambda: "YouTube")
    client = TestClient(app)
    headers = register_user(client, f"collection-{uuid4().hex}@example.com")
    other_headers = register_user(client, f"other-{uuid4().hex}@example.com")
    session_id = client.post("/sessions/start", headers=headers).json()["id"]

    assert client.post(
        f"/sessions/{session_id}/labels",
        headers=headers,
        json={
            "start_elapsed_seconds": 0,
            "end_elapsed_seconds": 0.001,
            "label": "focused",
        },
    ).status_code == 409
    assert client.post(
        f"/sessions/{session_id}/collection/consent",
        headers=other_headers,
        json={"consent": True},
    ).status_code == 404
    consent = client.post(
        f"/sessions/{session_id}/collection/consent",
        headers=headers,
        json={"consent": True},
    )
    assert consent.status_code == 200
    assert consent.json()["consent"] is True
    status = client.get(
        f"/sessions/{session_id}/collection",
        headers=headers,
    )
    assert status.status_code == 200
    assert status.json()["consent"] is True

    sleep(0.02)
    success, encoded = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    assert success
    frame_response = client.post(
        "/attention/frame",
        content=encoded.tobytes(),
        headers={**headers, "Content-Type": "image/jpeg"},
    )
    assert frame_response.status_code == 200
    assert "features" not in frame_response.json()
    telemetry = isolate_api_database.connection.execute(
        "SELECT app_name, app_category, features_json FROM telemetry WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    collected_features = json.loads(telemetry["features_json"])
    assert telemetry["app_name"] == "YouTube"
    assert telemetry["app_category"] == "distracting"
    assert collected_features["active_app_category"] == "distracting"
    assert "app_name" not in collected_features

    label = client.post(
        f"/sessions/{session_id}/labels",
        headers=headers,
        json={
            "start_elapsed_seconds": 0,
            "end_elapsed_seconds": 0.01,
            "label": "focused",
        },
    )
    assert label.status_code == 201
    assert label.json()["source"] == "self_reported"

    exported = client.get(
        f"/sessions/{session_id}/dataset.csv",
        headers=headers,
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "perclos" in exported.text
    assert "focused" in exported.text
    assert "image" not in exported.text
    assert "frame" not in exported.text


def test_revoking_collection_consent_deletes_collected_features_and_labels(
    isolate_api_database,
) -> None:
    client = TestClient(app)
    headers = register_user(client, f"revoke-{uuid4().hex}@example.com")
    session_id = client.post("/sessions/start", headers=headers).json()["id"]
    database = isolate_api_database
    user_id = database.connection.execute(
        "SELECT user_id FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()["user_id"]
    database.set_collection_consent(session_id, user_id, True)
    database.create_label(session_id, user_id, 0, 0.5, "focused")

    response = client.post(
        f"/sessions/{session_id}/collection/consent",
        headers=headers,
        json={"consent": False},
    )

    assert response.status_code == 200
    assert database.collection_is_consented(session_id) is False
    assert database.connection.execute(
        "SELECT COUNT(*) FROM labels WHERE session_id = ?", (session_id,)
    ).fetchone()[0] == 0
    assert client.get(
        f"/sessions/{session_id}/dataset.csv", headers=headers
    ).status_code == 409


def test_missing_trained_model_is_reported_for_rules_fallback(
    isolate_api_database, monkeypatch
) -> None:
    monkeypatch.delenv("FOCUS_GUARD_MODEL_PATH", raising=False)

    model = main._model_inference_for(123)

    assert model is None
    assert "No trained model is registered" in main.user_model_errors[123]


def test_privacy_export_delete_and_retention_endpoints() -> None:
    client = TestClient(app)
    owner_headers = register_user(client, f"privacy-{uuid4().hex}@example.com")
    other_headers = register_user(client, f"private-{uuid4().hex}@example.com")
    session_id = client.post("/sessions/start", headers=owner_headers).json()["id"]

    exported = client.get("/data/export.json", headers=owner_headers)
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].endswith(
        'filename="focus-guard-export.json"'
    )
    assert [session["id"] for session in exported.json()["sessions"]] == [session_id]
    assert client.get("/data/export.json", headers=other_headers).json()["sessions"] == []

    assert client.get("/privacy/retention", headers=owner_headers).json() == {
        "retention_days": None
    }
    configured = client.put(
        "/privacy/retention",
        headers=owner_headers,
        json={"retention_days": 30},
    )
    assert configured.status_code == 200
    assert configured.json()["retention_days"] == 30
    assert client.put(
        "/privacy/retention",
        headers=owner_headers,
        json={"retention_days": 0},
    ).status_code == 422

    assert client.delete(
        f"/sessions/{session_id}", headers=other_headers
    ).status_code == 404
    assert client.delete(
        f"/sessions/{session_id}", headers=owner_headers
    ).status_code == 200
    assert client.get("/history", headers=owner_headers).json() == []

    client.post("/sessions/start", headers=owner_headers)
    deleted = client.delete("/data", headers=owner_headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True, "deleted_sessions": 1}
    assert client.get("/history", headers=owner_headers).json() == []


def test_browser_domain_bridge_requires_local_token_and_stores_domain_only(
    monkeypatch,
) -> None:
    class FakeAnalyzer:
        def process(self, frame):
            return VisionSnapshot(
                face_present=True,
                blink_rate=0.0,
                ear=0.3,
                gaze="looking_at_screen",
            )

    monkeypatch.setenv("FOCUS_GUARD_BROWSER_TOKEN", "test-local-browser-secret")
    monkeypatch.setattr("backend.main.get_active_application", lambda: "YouTube - Google Chrome")
    monkeypatch.setattr("backend.main._face_analyzer_for", lambda user_id: FakeAnalyzer())
    client = TestClient(app, client=("127.0.0.1", 50000))
    headers = register_user(client, f"browser-{uuid4().hex}@example.com")
    session_id = client.post("/sessions/start", headers=headers).json()["id"]

    assert client.post(
        f"/sessions/{session_id}/context/browser",
        json={"domain": "www.youtube.com"},
    ).status_code == 401
    rule = client.put(
        "/context/category-rules",
        headers=headers,
        json={
            "rule_type": "domain",
            "rule_value": "youtube.com",
            "category": "distracting",
        },
    )
    assert rule.status_code == 200
    assert rule.json()["rule_value"] == "youtube.com"
    assert client.post(
        f"/sessions/{session_id}/context/browser",
        headers={"X-Focus-Guard-Token": "test-local-browser-secret"},
        json={"domain": "www.youtube.com"},
    ).json()["category"] == "distracting"
    assert client.post(
        f"/sessions/{session_id}/context/browser",
        headers={"X-Focus-Guard-Token": "test-local-browser-secret"},
        json={"domain": "https://youtube.com/watch?v=private"},
    ).status_code == 422

    success, encoded = cv2.imencode(".jpg", np.zeros((32, 32, 3), dtype=np.uint8))
    assert success
    score = client.post(
        "/attention/frame",
        content=encoded.tobytes(),
        headers={**headers, "Content-Type": "image/jpeg"},
    )

    assert score.status_code == 200
    assert score.json()["app_category"] == "distracting"
    context_rows = main.database.connection.execute(
        "SELECT domain, category FROM browser_context"
    ).fetchall()
    assert [dict(row) for row in context_rows] == [
        {"domain": "www.youtube.com", "category": "distracting"}
    ]
    assert "private" not in repr(context_rows)
    assert client.get("/context/browser", headers=headers).json()["domain"] == "www.youtube.com"


def test_analytics_endpoints_are_authenticated_and_return_empty_cells() -> None:
    client = TestClient(app)
    headers = register_user(client, f"analytics-{uuid4().hex}@example.com")

    assert client.get("/analytics/weekly").status_code == 401
    weekly = client.get("/analytics/weekly", headers=headers)
    assert weekly.status_code == 200
    assert weekly.json()["daily"] == []
    assert weekly.json()["comparison"]["current"]["total_focus_seconds"] == 0
    heatmap = client.get("/analytics/heatmap", headers=headers)
    assert heatmap.status_code == 200
    assert len(heatmap.json()["cells"]) == 168
    assert all(cell["average_score"] is None for cell in heatmap.json()["cells"])
    assert client.get(
        "/analytics/weekly?start_date=2025-03-10&end_date=2025-03-01",
        headers=headers,
    ).status_code == 422


def test_insights_are_scoped_and_can_be_dismissed(isolate_api_database) -> None:
    client = TestClient(app)
    email = f"insights-{uuid4().hex}@example.com"
    headers = register_user(client, email)
    other_headers = register_user(client, f"no-insights-{uuid4().hex}@example.com")
    user_id = isolate_api_database.connection.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()["id"]
    session_id = client.post("/sessions/start", headers=headers).json()["id"]
    isolate_api_database.create_insight(
        user_id,
        session_id,
        "low_focus",
        "Consider taking a break.",
        1_000.0,
    )

    insights = client.get("/insights", headers=headers)
    assert insights.status_code == 200
    insight_id = insights.json()[0]["id"]
    assert client.get("/insights", headers=other_headers).json() == []
    assert client.post(
        f"/insights/{insight_id}/dismiss", headers=other_headers
    ).status_code == 404
    assert client.post(
        f"/insights/{insight_id}/dismiss", headers=headers
    ).json() == {"ok": True}
    assert client.post(
        f"/insights/{insight_id}/feedback",
        headers=other_headers,
        json={"feedback": "not_helpful"},
    ).status_code == 404
    assert client.post(
        f"/insights/{insight_id}/feedback",
        headers=headers,
        json={"feedback": "not_helpful"},
    ).json() == {"ok": True}
    updated = client.get("/insights", headers=headers).json()[0]
    assert updated["dismissed"] == 1
    assert updated["feedback"] == "not_helpful"


def test_sync_is_opt_in_and_scoped_to_device(isolate_api_database) -> None:
    client = TestClient(app)
    headers = register_user(client, f"sync-{uuid4().hex}@example.com")

    assert client.get("/sync", headers=headers).json() == []
    disabled = client.put(
        "/sync",
        headers=headers,
        json={"device_id": "browser-a", "device_name": "Test Browser", "enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] == 0
    assert client.get(
        "/sync/export",
        headers=headers,
        params={"device_id": "browser-a"},
    ).status_code == 409

    enabled = client.put(
        "/sync",
        headers=headers,
        json={"device_id": "browser-a", "device_name": "Test Browser", "enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] == 1
    exported = client.get(
        "/sync/export",
        headers=headers,
        params={"device_id": "browser-a"},
    )
    assert exported.status_code == 200
    assert "sessions" in exported.json()


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