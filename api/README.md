# Backup Monitor API

RESTful API (FastAPI) for monitoring and reporting a distributed backup system
(Kopia on NAS + Ceph Object Storage). This is the **center of the system** — the
web dashboard, NAS scripts, and metric collector all talk to it over HTTP/JSON.

## Stack
- Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic
- PostgreSQL, JWT (PyJWT), bcrypt, ReportLab

## Run with Docker (recommended)
From the repo root:
```bash
cp .env.example .env
docker compose up --build
```
With `AUTO_SEED=true` (default in `.env.example`), the API container waits for
Postgres, runs migrations, and seeds demo data automatically.

- API:   http://localhost:8000
- Docs:  http://localhost:8000/docs
- Health: http://localhost:8000/health

## Interactive API Docs
Swagger UI is available at `http://localhost:8000/docs`.

The documentation is grouped by operational role:
- **auth** — login, logout, refresh token, and current profile.
- **logs** — NAS backup result ingestion and failed-backup acknowledgement.
- **monitor** — NAS/Ceph metric ingestion, freshness status, and history.
- **reports** — generate and download PDF reports.
- **users** — admin-only user and machine-account management.

To try protected endpoints from Swagger:
1. Call `POST /api/auth/login`.
2. Copy the returned `access_token`.
3. Click **Authorize** and paste it as `Bearer <access_token>`.

Timestamp fields must include an explicit timezone offset, for example
`2026-07-10T09:00:00+07:00` or `2026-07-10T02:00:00Z`. The API stores instants
in UTC, while dashboard/report date ranges are interpreted in `APP_TIMEZONE`
(default: `Asia/Jakarta`).

## Manual migration / seed
If `AUTO_SEED=false` or you want to re-run:
```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
```

## Seed accounts
| username      | password     | role      |
|---------------|--------------|-----------|
| admin         | admin123     | admin     |
| operator      | operator     | operator  |
| nas-synology  | synology123  | service   |
| nas-wd        | wd123        | service   |
| collector     | collector123 | collector |

## Auth
- `POST /api/auth/login` — `{ "username", "password" }` → `{ access_token, user }`
- `POST /api/auth/refresh` — rotate current token for a fresh one (old is revoked)
- `POST /api/auth/logout` — **revokes** the current token (see below)
- `GET  /api/auth/me` — current user profile (requires Bearer token)

Tokens carry `iss`/`aud`/`nbf`/`jti` claims and are validated on every request.
Default access-token lifetime is 60 min; clients call `/api/auth/refresh` to stay
logged in.

Production safety checks are enabled with `APP_ENV=production`. In that mode the
API refuses to start if `AUTO_SEED=true` or `JWT_SECRET_KEY` is still a weak
default value.

## Backup Logs
- `POST  /api/logs/ingest` — NAS submits a Kopia result. Role: **service** only.
  `status` accepts `SUCCESS`/`FAILED` (case-insensitive), invalid → `422`.
  `raw_payload` stored as JSONB, `reported_by` taken from the JWT.
  Retries are idempotent for the same `(nas_id, job_name, snapshot_id)`:
  a new snapshot returns `201` with `created=true`; an existing snapshot
  returns `200` with `created=false` and does not create a duplicate row.
- `GET   /api/logs` — paginated list. Role: **admin/operator**. Filters: `nas_id`,
  `status`, `job_name`, `date_from`, `date_to`, `acknowledged`, `page`, `page_size`.
- `GET   /api/logs/{log_id}` — full detail incl. raw payload. Role: **admin/operator**.
- `PATCH /api/logs/{log_id}/acknowledge` — mark a FAILED log reviewed with a
  `remark`. Role: **admin/operator**. Non-FAILED → `400`.

## Monitoring
- `POST /api/monitor/ingest` — collector submits a metric batch. Role:
  **collector** only. Each metric becomes its own row (numeric → `metric_value`,
  string → `metric_text`).
- `GET  /api/monitor/summary` — NAS fresh/stale/offline counts + Ceph health.
- `GET  /api/monitor/nas` / `GET /api/monitor/nas/{nas_id}` — latest snapshot(s).
- `GET  /api/monitor/nas/{nas_id}/history?metric=cpu_usage` — metric history.
- `GET  /api/monitor/ceph` / `GET /api/monitor/ceph/history?metric=storage_used_pct`.
- `GET  /api/monitor/collector/status` — last collector run (admin, operator, or collector).
- `POST /api/monitor/collector/run-once` — record a manual trigger. Role: admin/operator.

**Freshness is computed by the API**, never the client:
`fresh` ≤ 90 s, `stale` ≤ 300 s, `offline` > 300 s or no data.

Send the token as `Authorization: Bearer <access_token>` on every request
except login.

### Token revocation (logout security)
JWTs are self-contained, so this API adds two server-side revocation mechanisms
so that logout takes effect immediately instead of waiting for token expiry:

1. **Per-token denylist (JTI).** Every token carries a unique `jti`. On
   `POST /api/auth/logout` that `jti` is stored in the `revoked_tokens` table
   until the token would have expired. The auth dependency rejects any token
   whose `jti` is on the denylist → that exact token returns `401` immediately.
   Other tokens for the same user keep working (precise, per-session logout).
2. **Bulk invalidation (`token_version`).** Each user has a `token_version`, and
   every token embeds `tv`. Bumping the user's `token_version` invalidates **all**
   of their existing tokens at once ("logout everywhere"). Used by password
   reset / token rotation in a later stage.

Expired denylist rows are purged lazily on each logout, so the table stays
small without a background job. Token lifetime is configurable via
`ACCESS_TOKEN_EXPIRE_MINUTES`.

## Timezone
The API stores instants in UTC. Business-day boundaries for dashboard filters
and reports use `APP_TIMEZONE` (default: `Asia/Jakarta`). Incoming timestamp
fields must include a timezone offset.

Examples:
- `2026-07-10T09:00:00+07:00`
- `2026-07-10T02:00:00Z`

## Tests
Recommended test command from the repository root:

```bash
docker compose run --rm --no-deps --entrypoint python api -m pytest -q
```

## Local (no Docker)
Requires a reachable PostgreSQL and a `.env` (or env vars) with `DATABASE_URL`
pointing at it:
```bash
cd api
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://backup_monitor:backup_monitor_pw@localhost:5432/backup_monitor
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```
