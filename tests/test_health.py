from fastapi.testclient import TestClient

from backend.main import app


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

    assert client.get("/admin/database/tables").status_code == 401

    tables_response = client.get("/admin/database/tables", auth=("admin", "admin123"))
    assert tables_response.status_code == 200
    assert {table["name"] for table in tables_response.json()} >= {
        "sessions",
        "telemetry",
        "users",
        "admins",
    }

    table_response = client.get(
        "/admin/database/tables/users?limit=1&offset=0",
        auth=("admin", "admin123"),
    )
    assert table_response.status_code == 200
    assert table_response.json()["name"] == "users"
    assert "columns" in table_response.json()
    assert len(table_response.json()["rows"]) <= 1
    assert client.get(
        "/admin/database/tables/not_a_table",
        auth=("admin", "admin123"),
    ).status_code == 404


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