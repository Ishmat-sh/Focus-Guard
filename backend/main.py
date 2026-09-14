from fastapi import FastAPI


app = FastAPI(title="Focus Guard API")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Focus Guard API is running", "docs": "/docs"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/focus-status")
def focus_status() -> dict[str, object]:
    return {
        "status": "idle",
        "session_length_minutes": 25,
        "break_length_minutes": 5,
        "is_active": False,
        "message": "Ready to focus",
    }
