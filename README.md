# NAS & Ceph Backup Monitor

Sistem pemantauan dan pelaporan pencadangan (*backup*) terdistribusi berbasis **Kopia** (di NAS) dan **Ceph Object Storage**, dengan **RESTful API** mandiri sebagai pusat kontrol sistem.

Proyek ini dibangun untuk memenuhi persyaratan **Kuliah Kerja Praktik (KKP)** di **PT Lucky Mom Indonesia**.

---

## Daftar Isi

- [Fitur Utama](#-fitur-utama)
- [Arsitektur Sistem](#-arsitektur-sistem)
- [Teknologi](#-teknologi)
- [Struktur Repositori](#-struktur-repositori)
- [Quick Start](#-quick-start)
- [Environment Variables](#-environment-variables)
- [Default Credentials](#-default-credentials)
- [Halaman Dashboard](#-halaman-dashboard)
- [API Endpoints](#-api-endpoints)
- [Role & Permissions](#-role--permissions)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Fitur Utama

| Kategori | Deskripsi |
|----------|-----------|
| **Centralized RESTful API** | Semua komunikasi berjalan melalui API berbasis FastAPI — tidak ada koneksi langsung ke database dari frontend. |
| **Role-Based Access Control** | JWT Bearer authentication dengan 4 role (`admin`, `operator`, `service`, `collector`), dilengkapi fitur token rotation dan denylist. |
| **Real-time Web Dashboard** | SPA React (Vite + Shadcn/UI + TailwindCSS) yang ter-containerize dengan Nginx. Mendukung Dark Mode. |
| **Metric Collector Daemon** | Layanan background independen yang memantau utilitas NAS via SNMP dan kesehatan klaster Ceph. Mendukung mode mock untuk demo. |
| **Automated PDF Reports** | Generate laporan PDF otomatis untuk periode tertentu menggunakan ReportLab, dengan opsi custom filename. |
| **Interactive Dashboard** | Chart yang bisa di-klik untuk drill-down ke data backup logs, kartu failed backup yang navigable. |
| **Resilient NAS Scripts** | Skrip Kopia di sisi NAS dengan fitur retry bawaan dan pending queue untuk menangani kondisi offline. |
| **User Management** | Pembuatan akun dinamis dengan auto-generated token (32 char) untuk akun mesin, serta dialog konfirmasi untuk aksi destruktif. |
| **Advanced Filtering** | Pencarian dan filtering berbasis dropdown pada semua halaman daftar (logs, reports, users). |

---

## 🏗️ Arsitektur Sistem

Seluruh komponen saling terhubung melalui satu titik pusat (REST API):

```text
 NAS (Kopia Script) ────────┐
                             │ POST /api/logs
                             ▼
                     ┌────────────────┐        ┌─────────────┐
                     │                │        │             │
 Metric Collector ──▶│  FastAPI (API) │◀──────▶│  PostgreSQL │
  (SNMP / Ceph)      │   Port 8000    │        │  Port 5432  │
                     └────────────────┘        └─────────────┘
                             ▲
                             │ GET/POST/PATCH/DELETE
                             │
                   ┌──────────────────┐
                   │  Web Dashboard   │
                   │  React + Nginx   │
                   │    Port 80       │
                   └──────────────────┘
```

> **Catatan**: Arsitektur ini dirancang *API-first* agar ke depannya aplikasi seluler Android dapat langsung terintegrasi tanpa modifikasi backend.

---

## 🛠 Teknologi

### Backend (API)
| Komponen | Teknologi |
|----------|-----------|
| Framework | FastAPI |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 |
| Migration | Alembic |
| Auth | JWT (PyJWT) + bcrypt |
| PDF | ReportLab |
| Serialization | Pydantic v2 |

### Frontend (Web Dashboard)
| Komponen | Teknologi |
|----------|-----------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite |
| UI Library | Shadcn/UI + Radix UI |
| Styling | TailwindCSS |
| Charts | Recharts |
| HTTP Client | Axios |
| State | TanStack Query (React Query) |
| Routing | React Router v6 |

### Infrastructure
| Komponen | Teknologi |
|----------|-----------|
| Containerization | Docker + Docker Compose |
| Web Server | Nginx (Alpine) |
| Collector | Python 3.12 (SNMP via pysnmp) |

---

## 📂 Struktur Repositori

```
nas-backup-monitor/
├── api/                        # Backend RESTful API
│   ├── app/
│   │   ├── models/             # SQLAlchemy models (User, BackupLog, Metric, Report, ...)
│   │   ├── routers/            # FastAPI route handlers (auth, logs, monitor, reports, users)
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── services/           # Business logic (auth, monitor, report, pdf)
│   │   ├── config.py           # Application settings
│   │   ├── database.py         # DB engine & session
│   │   ├── dependencies.py     # Auth dependencies & role guards
│   │   ├── security.py         # JWT token creation & verification
│   │   ├── seed.py             # Auto-seeder for demo data
│   │   └── main.py             # FastAPI app entrypoint
│   ├── alembic/                # Database migrations
│   ├── tests/                  # Unit tests (pytest)
│   ├── Dockerfile
│   ├── entrypoint.sh           # Migration + seed + start
│   └── requirements.txt
│
├── web-dashboard/              # Frontend SPA
│   ├── src/
│   │   ├── pages/              # Route pages
│   │   │   ├── Overview.tsx        # Dashboard utama (summary cards, chart, failed alerts)
│   │   │   ├── BackupLogs.tsx      # Daftar log backup (filter NAS, job, date)
│   │   │   ├── BackupLogDetail.tsx # Detail log + acknowledge failed backup
│   │   │   ├── MonitorNas.tsx      # Monitoring NAS (CPU, RAM, Disk, Uptime)
│   │   │   ├── MonitorCeph.tsx     # Monitoring Ceph cluster
│   │   │   ├── CollectorStatus.tsx # Status daemon collector
│   │   │   ├── Reports.tsx         # Generate & download PDF reports
│   │   │   ├── Users.tsx           # User management (CRUD, token rotation)
│   │   │   └── Login.tsx           # Halaman login
│   │   ├── components/         # Reusable UI components (Shadcn/UI)
│   │   ├── lib/                # Utilities (API client, auth context)
│   │   └── App.tsx             # React Router configuration
│   ├── Dockerfile
│   └── nginx.conf
│
├── collector/                  # Metric Collector Daemon
│   ├── metric_collector.py     # Main loop: SNMP NAS polling
│   ├── snmp_collector.py       # SNMP OID queries
│   ├── ceph_collector.py       # Ceph metrics via Prometheus endpoint
│   ├── Dockerfile
│   └── requirements.txt
│
├── nas-scripts/                # Client-side NAS scripts
│   ├── kopia_backup.sh         # Kopia backup + log ingest
│   ├── retry_pending_logs.sh   # Retry failed API submissions
│   └── pending/                # Queue directory for offline logs
│
├── docker-compose.yml          # Full stack orchestration
├── .env.example                # Template environment variables
└── README.md                   # ← Anda di sini
```

---

## ⚡ Quick Start

### Prasyarat

- **Docker** ≥ 20.x
- **Docker Compose Plugin** ≥ 2.x

### 1. Clone & Setup Environment

```bash
git clone <repository-url>
cd nas-backup-monitor

# Salin template environment variables
cp .env.example .env

# Edit .env sesuai kebutuhan (opsional untuk demo)
```

### 2. Build & Run

```bash
# Build dan jalankan seluruh stack (4 containers)
docker compose up -d --build
```

Perintah di atas akan membuat dan menjalankan:

| Container | Deskripsi | Port |
|-----------|-----------|------|
| `bm_postgres` | Database PostgreSQL 16 | `5433` (host) → `5432` (container) |
| `bm_api` | FastAPI Backend + Auto Migration + Auto Seed | `8000` |
| `bm_web` | Nginx serving React SPA | `80` |
| `bm_collector` | Metric collector daemon (SNMP/Ceph) | — (internal) |

### 3. Akses Layanan

| Layanan | URL |
|---------|-----|
| **Web Dashboard** | [http://localhost](http://localhost) |
| **API Documentation (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **API Health Check** | [http://localhost:8000/health](http://localhost:8000/health) |

---

## 🔧 Environment Variables

Konfigurasi utama melalui file `.env` di root project:

| Variable | Default | Deskripsi |
|----------|---------|-----------|
| `POSTGRES_USER` | `backup_monitor` | Username database |
| `POSTGRES_PASSWORD` | `backup_monitor_pw` | Password database |
| `POSTGRES_DB` | `backup_monitor` | Nama database |
| `POSTGRES_HOST_PORT` | `5433` | Port PostgreSQL di host |
| `JWT_SECRET_KEY` | `dev-secret-change-me` | **⚠️ Ubah di production!** Secret key untuk JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritma signing JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Masa berlaku token (menit) |
| `AUTO_SEED` | `true` | Otomatis isi data demo saat pertama kali start |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Allowed CORS origins |
| `COLLECTOR_INTERVAL_SECONDS` | `60` | Interval polling metrik (detik) |
| `USE_MOCK_METRICS` | `false` | Gunakan data simulasi (tanpa SNMP/Ceph asli) |
| `NAS_TARGETS` | `synology:ip,wd:ip` | Daftar NAS yang dipantau (format: `id:ip`) |
| `CEPH_METRICS_URL` | `http://...:9283/metrics` | URL endpoint Prometheus Ceph |

> **Tips Production**: Generate JWT secret yang aman dengan `openssl rand -hex 32`

---

## 🔑 Default Credentials

Saat `AUTO_SEED=true`, database akan otomatis diisi data demo. Gunakan kredensial berikut:

| Role | Username | Password | Kegunaan |
|------|----------|----------|----------|
| **Admin** | `admin` | `admin123` | Login ke Web Dashboard (full access) |
| **Operator** | — | — | Buat via menu User Management |
| **Service** | `nas-synology` | `synology123` | Autentikasi script backup di NAS Synology |
| **Service** | `nas-wd` | `wd123` | Autentikasi script backup di NAS WD |
| **Collector** | `collector` | `collector123` | Autentikasi layanan Metric Collector |

> **⚠️ Penting**: Ubah semua password default sebelum deploy ke production!

---

## 📊 Halaman Dashboard

| Halaman | Route | Deskripsi |
|---------|-------|-----------|
| **Overview** | `/dashboard` | Ringkasan sistem: total backup, success rate, chart aktivitas harian (klik bar untuk drill-down), kartu failed backup terbaru |
| **Backup Logs** | `/dashboard/logs` | Daftar semua log backup dengan filter NAS, job name, date range. Klik baris untuk detail |
| **Log Detail** | `/dashboard/logs/:id` | Detail lengkap log backup. Fitur acknowledge untuk backup yang gagal |
| **Monitor NAS** | `/dashboard/monitor/nas` | Real-time metrics NAS (CPU, RAM, Disk, Network, Uptime) |
| **Monitor Ceph** | `/dashboard/monitor/ceph` | Status klaster Ceph (health, usage, IOPS, OSD) |
| **Collector Status** | `/dashboard/monitor/collector` | Status terakhir daemon collector |
| **Reports** | `/dashboard/reports` | Generate dan download laporan PDF. Mendukung custom filename dan filter NAS |
| **User Management** | `/dashboard/users` | CRUD akun, token rotation, role assignment (Admin only) |

---

## 📡 API Endpoints

Semua endpoint berada di bawah prefix `/api`. Dokumentasi interaktif tersedia di `/docs` (Swagger UI).

### Auth
| Method | Endpoint | Deskripsi | Auth |
|--------|----------|-----------|------|
| `POST` | `/api/auth/login` | Login, mendapatkan JWT token | — |
| `POST` | `/api/auth/logout` | Logout, invalidasi token | Bearer |
| `GET` | `/api/auth/me` | Profil user yang sedang login | Bearer |

### Backup Logs
| Method | Endpoint | Deskripsi | Auth |
|--------|----------|-----------|------|
| `GET` | `/api/logs` | Daftar log backup (dengan query filter) | Bearer |
| `GET` | `/api/logs/{id}` | Detail satu log | Bearer |
| `POST` | `/api/logs` | Kirim log baru (dari NAS script) | Service |
| `PATCH` | `/api/logs/{id}/acknowledge` | Acknowledge backup gagal | Admin/Operator |

### Monitoring
| Method | Endpoint | Deskripsi | Auth |
|--------|----------|-----------|------|
| `GET` | `/api/monitor/nas` | Daftar NAS ID yang terdaftar | Bearer |
| `GET` | `/api/monitor/nas/{source_id}/latest` | Metrik terbaru NAS tertentu | Bearer |
| `GET` | `/api/monitor/ceph/latest` | Metrik terbaru Ceph | Bearer |
| `POST` | `/api/monitor/push` | Push metrik dari collector | Collector |

### Reports
| Method | Endpoint | Deskripsi | Auth |
|--------|----------|-----------|------|
| `GET` | `/api/reports` | Daftar report yang sudah digenerate | Admin/Operator |
| `POST` | `/api/reports/generate` | Generate laporan PDF baru | Admin/Operator |
| `GET` | `/api/reports/{id}/download` | Download file PDF | Admin/Operator |
| `DELETE` | `/api/reports/{id}` | Hapus report | Admin |

### Users
| Method | Endpoint | Deskripsi | Auth |
|--------|----------|-----------|------|
| `GET` | `/api/users` | Daftar semua user | Admin |
| `POST` | `/api/users` | Buat user baru | Admin |
| `PUT` | `/api/users/{id}` | Update user | Admin |
| `DELETE` | `/api/users/{id}` | Disable user | Admin |
| `POST` | `/api/users/{id}/rotate-token` | Generate password baru | Admin |

---

## 👥 Role & Permissions

| Permission | Admin | Operator | Service | Collector |
|------------|:-----:|:--------:|:-------:|:---------:|
| Login ke Dashboard | ✅ | ✅ | ❌ | ❌ |
| Lihat Overview & Logs | ✅ | ✅ | ❌ | ❌ |
| Lihat Monitoring | ✅ | ✅ | ❌ | ❌ |
| Acknowledge Failed Backup | ✅ | ✅ | ❌ | ❌ |
| Generate & Download Report | ✅ | ✅ | ❌ | ❌ |
| Manage Users | ✅ | ❌ | ❌ | ❌ |
| Delete Reports | ✅ | ❌ | ❌ | ❌ |
| Push Backup Logs (API) | ❌ | ❌ | ✅ | ❌ |
| Push Metrics (API) | ❌ | ❌ | ❌ | ✅ |

---

## 🔨 Development

### Menjalankan API secara lokal (tanpa Docker)

```bash
cd api/

# Buat virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Jalankan migration
alembic upgrade head

# Jalankan server
uvicorn app.main:app --reload --port 8000
```

### Menjalankan Web Dashboard secara lokal

```bash
cd web-dashboard/

# Install dependencies
npm install

# Jalankan dev server
npm run dev
```

> Pastikan API sudah berjalan di `http://localhost:8000` agar dashboard dapat berkomunikasi.

### Rebuild Container Tertentu

```bash
# Rebuild hanya API (setelah mengubah backend code)
docker compose build api && docker compose up -d api

# Rebuild hanya Web Dashboard (setelah mengubah frontend code)
docker compose build web-dashboard && docker compose up -d web-dashboard

# Rebuild semua
docker compose up -d --build
```

### Menjalankan Tests

```bash
cd api/
pytest
```

### Database Migration

```bash
cd api/

# Buat migration baru
alembic revision --autogenerate -m "deskripsi perubahan"

# Apply migration
alembic upgrade head
```

---

## 🔍 Troubleshooting

### Reset Database dari Awal
```bash
docker compose down -v
docker compose up -d --build
```
> **⚠️ Warning**: Flag `-v` akan menghapus semua data di volume PostgreSQL dan reports.

### API Tidak Memuat Kode Terbaru
Container API menggunakan `build`, bukan volume mount. Setelah mengubah kode backend, **wajib rebuild**:
```bash
docker compose build api && docker compose up -d api
```
> `docker compose restart api` **tidak cukup** — hanya me-restart container lama tanpa mengkompilasi ulang image.

### Port Sudah Digunakan
Jika port `5432` sudah digunakan oleh PostgreSQL lokal, ubah `POSTGRES_HOST_PORT` di file `.env`:
```env
POSTGRES_HOST_PORT=5433
```

### Melihat Log Container
```bash
# Semua container
docker compose logs -f

# Container tertentu
docker compose logs -f api
docker compose logs -f web-dashboard
docker compose logs -f collector
```

### Collector Tidak Mendapat Data
1. Pastikan `NAS_TARGETS` di `.env` berisi IP yang benar dan reachable
2. Untuk demo tanpa NAS/Ceph fisik, set `USE_MOCK_METRICS=true`
3. Periksa log collector: `docker compose logs -f collector`

---

## 📄 Lisensi

Proyek ini dikembangkan sebagai bagian dari program **Kuliah Kerja Praktik (KKP)** dan bersifat internal untuk **PT Lucky Mom Indonesia**.
