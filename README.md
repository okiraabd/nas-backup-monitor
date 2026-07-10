# NAS & Ceph Backup Monitor

Sistem pemantauan dan pelaporan backup terdistribusi untuk NAS yang menjalankan
**Kopia** dan storage backend **Ceph Object/S3**. Proyek ini dibuat untuk
kebutuhan KKP di PT Lucky Mom Indonesia.

Inti desainnya sederhana: semua komponen berbicara ke **FastAPI REST API**.
Frontend, collector, dan reporter NAS tidak pernah mengakses database secara
langsung.

## Ringkasan komponen

| Komponen | Fungsi |
|---|---|
| `api/` | FastAPI pusat data: auth, backup logs, monitoring, reports, user management. |
| `web-dashboard/` | React SPA yang disajikan oleh Nginx. |
| `collector/` | Daemon Python untuk membaca SNMP exporter/Ceph metrics dan mengirim metrik ke API. |
| `snmp-exporter/` | Template konfigurasi SNMP Exporter untuk Synology dan WD PR4100. |
| `nas-scripts/` | Reporter di NAS untuk membaca snapshot Kopia dan mengirim hasil backup ke API. |
| `postgres` | Database utama untuk user, log backup, metric, report metadata, dan token revocation. |

## Fitur utama

- Dashboard web untuk overview, backup logs, monitoring NAS/Ceph, reports, dan user management.
- JWT authentication dengan role `admin`, `operator`, `service`, dan `collector`.
- Backup log ingest idempotent berdasarkan `nas_id + job_name + snapshot_id`.
- NAS reporter tidak menjalankan backup; Kopia tetap mengatur backup, schedule, retention, dan upload.
- Metric collector mendukung mode real dan mock.
- PDF report per periode tanggal lokal.
- Timezone aplikasi terpusat via `APP_TIMEZONE`, default `Asia/Jakarta`.
- OpenAPI/Swagger docs informatif di `/docs`.

## Arsitektur

```text
NAS Kopia Reporter ── POST /api/logs/ingest ─┐
                                             │
Metric Collector ─ POST /api/monitor/ingest ├── FastAPI API ── PostgreSQL
                                             │
Web Dashboard ───── GET/POST/PATCH /api/* ──┘
```

Untuk monitoring NAS production, NAS cukup expose SNMP UDP/161. Collector tidak
query SNMP langsung; collector membaca SNMP Exporter:

```text
NAS SNMP ── UDP/161 ──> SNMP Exporter ── /snmp?target=<ip>&module=<module> ──> Collector
```

Data waktu disimpan dan dibandingkan sebagai UTC. Tampilan dashboard, filter
tanggal, dan report menggunakan timezone aplikasi (`APP_TIMEZONE`).

## Struktur repositori

```text
nas-backup-monitor/
├── api/
│   ├── app/
│   │   ├── models/        # SQLAlchemy models
│   │   ├── routers/       # FastAPI endpoints
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── services/      # Business logic
│   │   ├── config.py      # Environment-based settings
│   │   ├── database.py    # Engine/session dependency
│   │   ├── dependencies.py# Auth/RBAC dependencies
│   │   ├── security.py    # Password hashing + JWT helpers
│   │   ├── timezone.py    # Local timezone helpers
│   │   └── main.py        # FastAPI app + OpenAPI metadata
│   ├── alembic/           # Database migrations
│   └── tests/             # Pytest suite
├── web-dashboard/
│   ├── src/
│   │   ├── pages/         # Dashboard pages
│   │   ├── components/    # Layout + UI components
│   │   └── lib/           # API client, auth, datetime utilities
│   ├── Dockerfile
│   └── nginx.conf
├── collector/
│   ├── metric_collector.py
│   ├── snmp_collector.py
│   └── ceph_collector.py
├── snmp-exporter/
│   ├── generator.yml     # Template module Synology/WD untuk snmp_exporter
│   └── mibs/             # Lokasi sementara MIB saat generate snmp.yml
├── nas-scripts/
│   ├── kopia_snapshot_reporter.sh
│   ├── kopia_reporter.py
│   └── .env.example
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start dengan Docker

Prasyarat:

- Docker Engine
- Docker Compose plugin

Jalankan dari root repo:

```bash
cp .env.example .env
docker compose up -d --build
```

Layanan default:

| Layanan | URL |
|---|---|
| Web dashboard | http://localhost |
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

Container:

| Container | Fungsi | Port host |
|---|---|---|
| `bm_postgres` | PostgreSQL | `${POSTGRES_HOST_PORT:-5433}` |
| `bm_api` | FastAPI + Alembic migration | `${API_HOST_PORT:-8000}` |
| `bm_web` | Nginx static web dashboard | `${WEB_HOST_PORT:-80}` |
| `bm_collector` | Metric collector daemon | internal only |
| `bm_snmp_exporter` | Optional SNMP Exporter profile `snmp` | `${SNMP_EXPORTER_HOST_BIND:-127.0.0.1}:${SNMP_EXPORTER_HOST_PORT:-9116}` |

## Environment penting

Semua konfigurasi utama berada di `.env`.

| Variable | Fungsi | Catatan |
|---|---|---|
| `APP_ENV` | Mode aplikasi: `development` atau `production`. | Production mengaktifkan safety check. |
| `APP_TIMEZONE` | Timezone bisnis/tampilan. | Default `Asia/Jakarta`. |
| `WEB_HOST_PORT` | Port dashboard di host. | Default `80`, container tetap `80`. |
| `API_HOST_PORT` | Port API di host. | Default `8000`, container tetap `8000`. |
| `POSTGRES_HOST_PORT` | Port PostgreSQL di host. | Default `5433`, container tetap `5432`. |
| `DATABASE_URL` | URL SQLAlchemy untuk API. | Host internal Compose: `postgres`. |
| `JWT_SECRET_KEY` | Secret signing JWT. | Wajib kuat di production. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Masa berlaku access token. | Default 60 menit. |
| `SEED_MODE` | Seed saat startup: `none`, `users`, atau `demo`. | `users` hanya akun; `demo` akun + data contoh. |
| `CORS_ORIGINS` | Origin frontend yang diizinkan. | Pisahkan dengan koma. |
| `REPORTS_DIR` | Lokasi PDF report di container API. | Default `/app/generated_reports`. |
| `COLLECTOR_USERNAME` | Akun role `collector`. | Dipakai service collector. |
| `COLLECTOR_PASSWORD` | Password akun collector. | Jangan commit nilai asli. |
| `COLLECTOR_INTERVAL_SECONDS` | Interval polling metric. | Default 60 detik. |
| `USE_MOCK_METRICS` | Aktifkan metric dummy. | Cocok untuk demo. |
| `SNMP_EXPORTER_IMAGE` | Image SNMP Exporter. | Pin tag di production. |
| `SNMP_EXPORTER_HOST_BIND` | IP bind port exporter di host. | Default `127.0.0.1`. |
| `SNMP_EXPORTER_HOST_PORT` | Port exporter di host. | Default `9116`. |
| `SNMP_EXPORTER_URL` | Endpoint SNMP Exporter terpusat. | Contoh `http://host:9116/snmp`. |
| `SNMP_DEFAULT_MODULE` | Module fallback SNMP Exporter. | Default `if_mib`. |
| `NAS_TARGETS` | Target NAS untuk collector. | Format `source_id\|ip\|module`. |
| `CEPH_METRICS_URL` | Endpoint Prometheus Ceph. | Contoh `http://host:9283/metrics`. |

Contoh hardening production:

```env
APP_ENV=production
SEED_MODE=none
JWT_SECRET_KEY=<hasil-openssl-rand-hex-32>
CORS_ORIGINS=https://dashboard.example.com
```

Jika `APP_ENV=production`, API akan gagal start bila `SEED_MODE=demo`,
`AUTO_SEED=true` legacy, atau `JWT_SECRET_KEY` masih default/lemah. Ini
disengaja agar konfigurasi demo tidak terbawa ke production.

## Seed akun dan data demo

Seed bersifat idempotent: dijalankan ulang tidak membuat duplikasi user atau
data demo yang sudah ada.

| Mode | Efek | Penggunaan yang disarankan |
|---|---|---|
| `SEED_MODE=none` | Tidak seed apapun. | Production normal setelah bootstrap. |
| `SEED_MODE=users` | Membuat akun awal saja. | Bootstrap awal tanpa data dummy. |
| `SEED_MODE=demo` | Membuat akun + backup log/metric demo. | Development/staging/demo. |

Akun awal berikut dibuat pada mode `users` dan `demo` jika belum ada:

| Username | Password | Role | Kegunaan |
|---|---|---|---|
| `admin` | `admin123` | `admin` | Login dashboard, full access. |
| `operator` | `operator` | `operator` | Lihat dashboard, acknowledge, generate report. |
| `nas-synology` | `synology123` | `service` | NAS reporter Synology/demo. |
| `nas-wd` | `wd123` | `service` | NAS reporter WD/demo. |
| `collector` | `collector123` | `collector` | Metric collector. |

Untuk production, gunakan `SEED_MODE=users` hanya saat bootstrap awal, lalu ubah
password/nonaktifkan akun yang tidak dipakai. Setelah itu kembalikan ke
`SEED_MODE=none`.

## Role dan permission

| Aksi | Admin | Operator | Service | Collector |
|---|:---:|:---:|:---:|:---:|
| Login dashboard | ✅ | ✅ | ❌ | ❌ |
| Melihat overview/log/monitoring | ✅ | ✅ | ❌ | ❌ |
| Acknowledge failed backup | ✅ | ✅ | ❌ | ❌ |
| Generate/download report | ✅ | ✅ | ❌ | ❌ |
| Delete report | ✅ | ❌ | ❌ | ❌ |
| Manage users | ✅ | ❌ | ❌ | ❌ |
| Ingest backup logs | ❌ | ❌ | ✅ | ❌ |
| Ingest metrics | ❌ | ❌ | ❌ | ✅ |

## Endpoint utama

Dokumentasi lengkap tersedia di Swagger: `http://localhost:8000/docs`.

| Area | Endpoint penting |
|---|---|
| Auth | `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me` |
| Backup logs | `POST /api/logs/ingest`, `GET /api/logs`, `GET /api/logs/{id}`, `PATCH /api/logs/{id}/acknowledge` |
| Monitoring | `POST /api/monitor/ingest`, `GET /api/monitor/summary`, `GET /api/monitor/activity-trend`, `GET /api/monitor/nas`, `GET /api/monitor/ceph` |
| Collector | `GET /api/monitor/collector/status`, `POST /api/monitor/collector/run` |
| Reports | `GET /api/reports`, `POST /api/reports/generate`, `GET /api/reports/{id}/download`, `DELETE /api/reports/{id}` |
| Users | `GET /api/users`, `POST /api/users`, `PATCH /api/users/{id}`, `PATCH /api/users/{id}/password`, `POST /api/users/{id}/rotate-token` |

Timestamp request harus membawa timezone offset eksplisit, misalnya
`2026-07-10T09:00:00+07:00` atau `2026-07-10T02:00:00Z`.

## Workflow SNMP monitoring NAS

Production direkomendasikan memakai SNMP Exporter terpusat di server Linux yang
bisa menjangkau semua NAS. Project ini menyediakan service SNMP Exporter
opsional lewat Compose profile `snmp`; jika exporter sudah berjalan di server
lain, cukup arahkan `SNMP_EXPORTER_URL` ke server tersebut.

Prinsipnya:

1. Synology/WD hanya membuka SNMP UDP/161 ke server SNMP Exporter.
2. SNMP Exporter memakai module sesuai tipe NAS:
   - `synology_nas`
   - `wd_pr4100`
3. Collector membaca endpoint HTTP exporter:
   - `/snmp?target=<ip_synology>&module=synology_nas`
   - `/snmp?target=<ip_wd>&module=wd_pr4100`
4. Collector menormalisasi hasilnya menjadi metric dashboard:
   - `cpu_usage`
   - `ram_used_pct`
   - `disk_used_pct`
   - `temperature`
   - `system_uptime`
   - `snmp_reachable`

Menjalankan SNMP Exporter bawaan project:

```bash
cp snmp-exporter/snmp.yml.example snmp-exporter/snmp.yml
# default SNMP v2 community adalah "public"; edit jika NAS memakai community lain
docker compose --profile snmp up -d snmp-exporter
```

Contoh konfigurasi collector jika memakai exporter bawaan Compose:

```env
SNMP_EXPORTER_URL=http://snmp-exporter:9116/snmp?auth=kkp_snmp_v2
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100
```

Contoh jika memakai exporter external:

```env
SNMP_EXPORTER_URL=http://snmp-exporter.example.lan:9116/snmp?auth=kkp_snmp_v2
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100
```

Template generator SNMP Exporter ada di [snmp-exporter/README.md](snmp-exporter/README.md).

## Workflow NAS reporter

Reporter NAS berada di `nas-scripts/`.

Prinsipnya:

1. Kopia tetap menjalankan backup sesuai policy/schedule.
2. Reporter membaca `kopia snapshot list --json` dari container Kopia.
3. Reporter merekonsiliasi snapshot baru berdasarkan snapshot ID.
4. Payload dikirim ke `POST /api/logs/ingest`.
5. Jika API/network bermasalah, payload disimpan di pending queue lokal.

Instalasi production NAS direkomendasikan di satu folder:

```text
/opt/nas-backup-monitor/
  kopia_snapshot_reporter.sh
  kopia_reporter.py
  .env
  secrets/
  runtime/
  logs/
```

Lihat detail di [nas-scripts/README.md](nas-scripts/README.md).

## Development

### API

Disarankan menjalankan test API di container agar sama dengan runtime:

```bash
docker compose run --rm --no-deps --entrypoint python api -m pytest -q
```

Untuk development lokal:

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Web dashboard

```bash
cd web-dashboard
npm install
npm run dev
```

Frontend dev server berjalan di `http://localhost:5173`. API base URL untuk dev
dibaca dari `VITE_API_BASE_URL` di root `.env`.

### Rebuild service

```bash
docker compose up -d --build api
docker compose up -d --build web-dashboard
docker compose up -d --build collector
```

`docker compose restart` hanya restart container lama; gunakan `up -d --build`
jika ada perubahan kode.

## Operasional dan best practice

- Jangan commit `.env`, password, token, file PDF report, cache, atau folder runtime.
- Gunakan `APP_ENV=production`, `SEED_MODE=none`, dan JWT secret kuat untuk production.
- Jalankan API di balik TLS/reverse proxy untuk akses production.
- Batasi exposure PostgreSQL; port host DB hanya perlu untuk administrasi lokal.
- Backup volume Docker `pgdata` dan `reports` jika data perlu dipertahankan.
- Untuk NAS, simpan reporter di path persistent seperti `/opt/nas-backup-monitor`.

## Troubleshooting

### API tidak memuat kode terbaru

```bash
docker compose up -d --build api
docker compose logs -f api
```

### Reset database dan report volume

```bash
docker compose down -v
docker compose up -d --build
```

Perintah ini menghapus volume PostgreSQL dan reports.

### Collector tidak mengirim metric

```bash
docker compose logs -f collector
```

Periksa:

- `COLLECTOR_USERNAME` / `COLLECTOR_PASSWORD`
- `NAS_TARGETS`
- `CEPH_METRICS_URL`
- konektivitas ke SNMP exporter NAS dan Ceph endpoint

### Cek migration dan health API

```bash
docker compose exec api alembic current
curl http://localhost:8000/health
```

## Lisensi / konteks

Proyek ini dikembangkan sebagai bagian dari program KKP dan bersifat internal
untuk PT Lucky Mom Indonesia.
