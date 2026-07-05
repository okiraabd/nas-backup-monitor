"""Pytest fixtures: in-memory SQLite DB, seeded users, and an API test client.

Tests run without Docker/Postgres. JSONB columns fall back to JSON on SQLite
via the model's with_variant() definition.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.backup_log import BackupLog
from app.models.collector_run import CollectorRun
from app.models.metric import Metric
from app.models.user import User
from app.security import hash_password

# One shared in-memory SQLite database for the whole test session.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed(db):
    now = datetime.now(timezone.utc)
    users = {
        "admin": User(username="admin", password_hash=hash_password("admin123"),
                      display_name="Administrator", role="admin", is_active=True),
        "nas-wd": User(username="nas-wd", password_hash=hash_password("wd123"),
                       display_name="NAS WD", role="service", is_active=True),
        "collector": User(username="collector", password_hash=hash_password("collector123"),
                          display_name="Collector", role="collector", is_active=True),
    }
    db.add_all(users.values())
    db.flush()

    db.add(BackupLog(nas_id="wd-pr4100", job_name="backup-finance", status="SUCCESS",
                     backup_engine="kopia", total_size_bytes=1000, created_at=now,
                     started_at=now, reported_by=users["nas-wd"].id))
    db.add(BackupLog(nas_id="wd-pr4100", job_name="backup-hrd", status="FAILED",
                     backup_engine="kopia", message="S3 error", created_at=now,
                     started_at=now, reported_by=users["nas-wd"].id, acknowledged=False))

    db.add(Metric(collected_at=now, source_type="nas", source_id="synology-ds1522",
                  metric_name="cpu_usage", metric_value=25, unit="%",
                  collected_by=users["collector"].id))
    db.add(CollectorRun(started_at=now - timedelta(seconds=3), finished_at=now,
                        status="SUCCESS", mode="demo", message="ok",
                        total_sources=3, success_sources=3, failed_sources=0))
    db.commit()


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        _seed(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(client: TestClient, username: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture()
def admin_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'admin', 'admin123')}"}


@pytest.fixture()
def service_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'nas-wd', 'wd123')}"}


@pytest.fixture()
def collector_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'collector', 'collector123')}"}
