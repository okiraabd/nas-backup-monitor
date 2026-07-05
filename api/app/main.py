"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, logs, monitor, reports, users

app = FastAPI(
    title="Backup Monitor API",
    description=(
        "RESTful API for monitoring and reporting a distributed backup system "
        "(Kopia on NAS + Ceph Object Storage) for PT Lucky Mom Indonesia."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness probe — does not require auth."""
    return {"status": "ok"}


# --- Routers (all under /api) ---
app.include_router(auth.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(monitor.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(users.router, prefix="/api")
