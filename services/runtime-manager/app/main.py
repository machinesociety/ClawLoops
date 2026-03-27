from fastapi import FastAPI

from app.api.internal import router as internal_router

app = FastAPI(title="clawloops-runtime-manager")
app.include_router(internal_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/readyz")
def readyz() -> dict[str, str]:
    return {"status": "ready"}
