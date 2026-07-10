"""FastAPI application entrypoint and OpenAPI documentation metadata."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, logs, monitor, reports, users

API_DESCRIPTION = """
Central REST API for the NAS Backup Monitor project.

This service receives backup results from NAS-side Kopia reporter scripts,
receives infrastructure metrics from the collector, stores everything in
PostgreSQL, and exposes the data to the web dashboard.

Operational notes:
- All timestamps are stored/compared as UTC instants.
- User-facing date ranges are interpreted in the configured local timezone
  (`APP_TIMEZONE`, default: `Asia/Jakarta`).
- Browser users authenticate with JWT bearer tokens.
- NAS reporter scripts use service accounts.
- Metric collectors use collector accounts.
"""

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Unauthenticated probes used by Docker or load balancers.",
    },
    {
        "name": "auth",
        "description": "Login, logout, token refresh, and current-user profile.",
    },
    {
        "name": "logs",
        "description": (
            "Backup result ingestion and review workflow. NAS service accounts "
            "write logs; admin/operator users read and acknowledge them."
        ),
    },
    {
        "name": "monitor",
        "description": (
            "NAS/Ceph metric ingestion, freshness summary, history, and collector "
            "run status."
        ),
    },
    {
        "name": "reports",
        "description": "Generate, list, download, and delete PDF backup reports.",
    },
    {
        "name": "users",
        "description": "Admin-only user and machine-account management.",
    },
]

app = FastAPI(
    title="Backup Monitor API",
    description=API_DESCRIPTION,
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["health"],
    summary="Check API liveness",
    description="Returns `ok` when the FastAPI process is running.",
)
def health() -> dict:
    """Liveness probe — does not require auth."""
    return {"status": "ok"}


# --- Routers (all under /api) ---
app.include_router(auth.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(monitor.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(users.router, prefix="/api")
