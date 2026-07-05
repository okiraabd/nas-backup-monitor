#!/usr/bin/env bash
# API container entrypoint: wait for DB, run migrations, optionally seed, then start.
set -e

echo "[entrypoint] Waiting for PostgreSQL at ${POSTGRES_HOST:-postgres}:${POSTGRES_PORT:-5432}..."
python - <<'PY'
import os, time, socket
host = os.environ.get("POSTGRES_HOST", "postgres")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            print("[entrypoint] PostgreSQL is reachable.")
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("[entrypoint] PostgreSQL not reachable, giving up.")
PY

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

if [ "${AUTO_SEED:-false}" = "true" ]; then
    echo "[entrypoint] AUTO_SEED=true -> seeding database..."
    python -m app.seed
fi

echo "[entrypoint] Starting API..."
exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
