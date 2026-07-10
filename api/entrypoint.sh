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

# SEED_MODE is the new explicit switch. AUTO_SEED is kept as a legacy fallback.
SEED_MODE_VALUE="${SEED_MODE:-}"
if [ -z "$SEED_MODE_VALUE" ]; then
    if [ "${AUTO_SEED:-false}" = "true" ]; then
        SEED_MODE_VALUE="demo"
    else
        SEED_MODE_VALUE="none"
    fi
fi

case "$SEED_MODE_VALUE" in
    none)
        echo "[entrypoint] SEED_MODE=none -> skipping seed."
        ;;
    users)
        echo "[entrypoint] SEED_MODE=users -> seeding accounts only..."
        python -m app.seed users
        ;;
    demo)
        echo "[entrypoint] SEED_MODE=demo -> seeding accounts and demo data..."
        python -m app.seed demo
        ;;
    *)
        echo "[entrypoint] Invalid SEED_MODE='$SEED_MODE_VALUE'. Use none, users, or demo."
        exit 1
        ;;
esac

echo "[entrypoint] Starting API..."
exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
