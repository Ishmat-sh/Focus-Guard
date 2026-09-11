from fastapi import FastAPI


app = FastAPI(title="Focus Guard API")


@app.get("/")
def root() -> dict[str, str]:
	return {"message": "Focus Guard API is running", "docs": "/docs"}


@app.get("/health")
def health_check() -> dict[str, str]:
	return {"status": "ok"}
