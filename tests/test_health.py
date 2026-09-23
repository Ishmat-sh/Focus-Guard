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