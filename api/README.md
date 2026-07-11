# Backup Monitor API

API adalah pusat data NAS & Ceph Backup Monitor. Service FastAPI ini
mengautentikasi seluruh klien, menyimpan data ke PostgreSQL, menghitung status
monitoring, dan membuat PDF report. Tidak ada komponen lain yang boleh
mengakses database secara langsung.

Dokumentasi sistem dan cara menjalankan stack ada di
[README root](../README.md).

## Tanggung jawab

- Mengeluarkan dan memvalidasi JWT untuk pengguna dashboard dan machine account.
- Menerima backup log dari reporter Kopia NAS.
- Menerima metric batch serta status siklus dari collector.
- Menyajikan log, status monitoring, history, dan tren untuk dashboard.
- Menghasilkan, menyimpan metadata, mengunduh, dan menghapus PDF report.
- Menjalankan migrasi Alembic ketika container dimulai.

~~~text
Reporter NAS ── POST /api/logs/ingest ─┐
Collector ──── POST /api/monitor/* ───┼──► FastAPI ───► PostgreSQL
Dashboard ──── GET/POST/PATCH /api/* ─┘       │
                                                └──► generated_reports/
~~~

## Teknologi dan struktur

| Area | Implementasi |
|---|---|
| Runtime | Python 3.12 dan Uvicorn |
| Web framework | FastAPI dan Pydantic v2 |
| Persistence | SQLAlchemy 2, PostgreSQL, Alembic |
| Security | bcrypt, PyJWT, HTTP Bearer, RBAC |
| Report | ReportLab |
| Test | pytest, FastAPI TestClient, SQLite in-memory |

~~~text
api/
├── app/
│   ├── routers/       # HTTP endpoint dan authorization per endpoint
│   ├── schemas/       # Kontrak request/response Pydantic
│   ├── models/        # ORM SQLAlchemy
│   ├── services/      # Auth, monitoring, report/PDF
│   ├── config.py      # Settings dari environment
│   ├── timezone.py    # Konversi batas tanggal lokal ↔ UTC
│   └── main.py        # App FastAPI, CORS, dan OpenAPI
├── alembic/           # Konfigurasi dan riwayat migrasi
├── tests/             # Test API terisolasi
├── entrypoint.sh      # Tunggu DB → migrasi → seed → Uvicorn
└── Dockerfile
~~~

## Menjalankan API

### Docker Compose

Cara yang direkomendasikan adalah menjalankan dari root proyek:

~~~bash
cp .env.example .env
# Edit kredensial, JWT_SECRET_KEY, dan SEED_MODE.
docker compose up -d --build postgres api
curl http://localhost:8000/health
~~~

Endpoint yang tersedia secara default:

| Endpoint | Kegunaan |
|---|---|
| http://localhost:8000/health | Liveness probe tanpa autentikasi. |
| http://localhost:8000/docs | Swagger UI / OpenAPI interaktif. |
| http://localhost:8000/openapi.json | Dokumen OpenAPI JSON. |

Container API melakukan urutan berikut:

1. Menunggu host PostgreSQL dapat dihubungi.
2. Menjalankan alembic upgrade head.
3. Menjalankan seed sesuai SEED_MODE.
4. Memulai Uvicorn pada port 8000.

### Local tanpa Docker

Anda memerlukan Python 3.12 dan PostgreSQL yang dapat dijangkau. Setel
DATABASE_URL dengan driver psycopg, lalu jalankan:

~~~bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/backup_monitor
alembic upgrade head
python -m app.seed users
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
~~~

Jangan gunakan kredensial atau JWT secret contoh pada environment production.
Lihat root .env.example untuk seluruh variabel service.

## Konfigurasi dan keamanan startup

| Variabel | Fungsi |
|---|---|
| DATABASE_URL | Koneksi SQLAlchemy. Dalam Compose, host normalnya adalah postgres. |
| APP_ENV | development, prod, atau production. Dua nilai terakhir mengaktifkan safety check. |
| JWT_SECRET_KEY | Secret penandatanganan token; wajib kuat dan non-default di production. |
| JWT_ALGORITHM | Default HS256. |
| JWT_ISSUER / JWT_AUDIENCE | Claim issuer/audience yang divalidasi saat decode token. |
| ACCESS_TOKEN_EXPIRE_MINUTES | Masa berlaku access token, default 60. |
| CORS_ORIGINS | Daftar origin dipisahkan koma untuk browser. |
| SEED_MODE | none, users, atau demo. |
| AUTO_SEED | Fallback legacy; true diperlakukan sebagai mode demo bila SEED_MODE kosong. |
| REPORTS_DIR | Direktori penyimpanan PDF, default /app/generated_reports. |
| APP_TIMEZONE | Zona IANA untuk batas hari report/tren, default Asia/Jakarta. |

Ketika APP_ENV adalah prod atau production, aplikasi gagal start jika:

- mode seed efektif adalah demo;
- AUTO_SEED=true dipakai sebagai fallback demo; atau
- JWT_SECRET_KEY adalah nilai lemah/default atau panjangnya kurang dari 32
  karakter.

Gunakan secret acak, misalnya dari openssl rand -hex 32, dan kelola di secret
store. Di Compose, report disimpan pada volume Docker bernama reports.

## Seed

| Mode | Perilaku |
|---|---|
| none | Tidak membuat data. Ini mode operasi normal setelah bootstrap. |
| users | Membuat akun awal saja bila belum ada. |
| demo | Membuat akun, backup logs, metrics, dan satu collector run contoh. |

Akun seed:

| Username | Password demo | Role |
|---|---|---|
| admin | admin123 | admin |
| operator | operator | operator |
| nas-synology | synology123 | service |
| nas-wd | wd123 | service |
| collector | collector123 | collector |

Seed idempoten. Untuk menjalankan ulang secara manual:

~~~bash
docker compose exec api python -m app.seed users
docker compose exec api python -m app.seed demo
~~~

Mode demo tidak boleh dianggap sebagai proses provisioning production. Setelah
akun bootstrap dibuat, reset atau rotasi secret machine account dan gunakan
SEED_MODE=none.

## Autentikasi, JWT, dan RBAC

Semua endpoint di bawah /api kecuali login memerlukan header berikut:

~~~text
Authorization: Bearer ACCESS_TOKEN
~~~

Token memuat subject, user ID, role, token version, issuer, audience, expiry,
not-before, issued-at, dan JWT ID (jti). API memverifikasi signature, expiry,
issuer, audience, akun aktif, serta token version pada setiap request.

Logout langsung berlaku karena API menggunakan dua mekanisme:

1. Logout atau refresh memasukkan jti token lama ke tabel revoked_tokens sampai
   token itu kadaluarsa.
2. Reset password, rotasi machine account, atau nonaktifkan user menaikkan
   token_version. Semua token lama untuk user itu segera invalid.

Baris revoke kadaluarsa dibersihkan saat logout/refresh berikutnya; tidak ada
worker background khusus untuk itu.

| Role | Hak utama |
|---|---|
| admin | Seluruh endpoint dashboard, report, dan manajemen user. |
| operator | Membaca data, acknowledge kegagalan, membuat/mengunduh report, meminta collector run. |
| service | Mengirim backup log dari NAS. |
| collector | Mengirim metric dan hasil collector run; membaca status collector. |

## Referensi endpoint

Swagger pada /docs adalah kontrak lengkap, termasuk schema dan contoh respons.
Tabel berikut adalah ringkasan operasional yang sesuai implementasi saat ini.

### Auth

| Method dan path | Role | Keterangan |
|---|---|---|
| POST /api/auth/login | Public | Tukar username/password menjadi access token dan profil user. |
| GET /api/auth/me | Semua token aktif | Profil token saat ini. |
| POST /api/auth/refresh | Semua token aktif | Revoke token lama dan mengeluarkan token baru. |
| POST /api/auth/logout | Semua token aktif | Revoke token saat ini. |

### Backup logs

| Method dan path | Role | Keterangan |
|---|---|---|
| POST /api/logs/ingest | service | Menerima satu hasil backup Kopia. |
| GET /api/logs | admin, operator | List berhalaman dan filter. |
| GET /api/logs/{log_id} | admin, operator | Detail log, termasuk raw payload. |
| PATCH /api/logs/{log_id}/acknowledge | admin, operator | Acknowledge log FAILED dengan remark wajib. |

POST /api/logs/ingest mengembalikan 201 untuk snapshot baru dan 200 untuk retry
snapshot yang sudah tersimpan. Idempotensi berlaku hanya ketika snapshot_id
ada, berdasarkan kombinasi nas_id, job_name, dan snapshot_id. Failure tanpa
snapshot_id sengaja dicatat sebagai event terpisah.

GET /api/logs menerima filter nas_id, status, job_name, date_from, date_to,
acknowledged, page, dan page_size. page_size berada pada rentang 1 sampai 100.
Hanya log berstatus FAILED yang dapat di-acknowledge.

### Monitoring dan collector

| Method dan path | Role | Keterangan |
|---|---|---|
| POST /api/monitor/ingest | collector | Menyimpan batch metric NAS atau Ceph. |
| GET /api/monitor/summary | admin, operator | Jumlah NAS dan ringkasan Ceph. |
| GET /api/monitor/activity-trend | admin, operator | Tren log SUCCESS/FAILED tujuh hari kalender lokal terakhir. |
| GET /api/monitor/nas | admin, operator | Snapshot metric terbaru semua NAS. |
| GET /api/monitor/nas/{nas_id} | admin, operator | Snapshot terbaru satu NAS. |
| GET /api/monitor/nas/{nas_id}/history | admin, operator | History satu metric NAS; parameter metric dan limit. |
| GET /api/monitor/ceph | admin, operator | Snapshot terbaru Ceph. |
| GET /api/monitor/ceph/history | admin, operator | History metric Ceph; metric, limit, dan source_id opsional. |
| GET /api/monitor/collector/status | admin, operator, collector | Hasil collector run terbaru. |
| POST /api/monitor/collector/run | collector | Mencatat satu collector run selesai. |
| POST /api/monitor/collector/run-once | admin, operator | Menambahkan marker PENDING, bukan mengeksekusi process collector langsung. |

Setiap metric dalam request ingest disimpan sebagai satu baris. Metric numeric
menjadi metric_value dan metric string menjadi metric_text. Tidak ada
deduplikasi atau retensi automatic untuk metric history.

Freshness dihitung di server dari metric terbaru per sumber:

| Status | Staleness |
|---|---|
| fresh | 0–90 detik |
| stale | lebih dari 90 hingga 300 detik |
| offline | lebih dari 300 detik atau belum ada data |

### Report dan user management

| Method dan path | Role | Keterangan |
|---|---|---|
| GET /api/reports | admin, operator | Daftar metadata report terbaru. |
| POST /api/reports/generate | admin, operator | Membuat PDF untuk periode tanggal lokal. |
| GET /api/reports/{report_id}/download | admin, operator | Mengunduh PDF tersimpan. |
| DELETE /api/reports/{report_id} | admin | Menghapus file dan metadata report. |
| GET /api/users | admin | Daftar user. |
| POST /api/users | admin | Membuat user. |
| GET /api/users/{user_id} | admin | Detail user. |
| PATCH /api/users/{user_id} | admin | Ubah display name, role, atau aktif/nonaktif. |
| DELETE /api/users/{user_id} | admin | Soft-delete: menonaktifkan akun. |
| PATCH /api/users/{user_id}/password | admin | Set password baru dan invalidate token lama. |
| POST /api/users/{user_id}/rotate-token | admin | Buat password baru sekali tampil untuk role service/collector. |

API melindungi dari hilangnya akses admin terakhir dan mencegah admin
menonaktifkan/menghapus akses adminnya sendiri.

## Kontrak waktu dan data

Semua timestamp masuk harus menyertakan offset zona waktu:

~~~text
2026-07-10T09:00:00+07:00
2026-07-10T02:00:00Z
~~~

Timestamp disimpan sebagai instant UTC. Untuk request report, date_from dan
date_to adalah tanggal tanpa waktu dan meliputi satu hari penuh menurut
APP_TIMEZONE. Filter log menerima timestamp. PDF report memuat:

- ringkasan SUCCESS/FAILED dan FAILED yang belum di-acknowledge;
- daftar backup log pada periode terpilih;
- detail kegagalan; serta
- snapshot monitoring terbaru saat report dibuat.

Filter NAS pada report menyaring backup log, sedangkan snapshot monitoring
tetap merepresentasikan semua sumber yang diketahui.

## Model data dan migrasi

| Tabel | Isi |
|---|---|
| users | Akun, role, bcrypt password hash, status aktif, dan token_version. |
| backup_logs | Hasil snapshot, detail ukuran/file, error, raw payload, dan acknowledge workflow. |
| metrics | Satu sample per metric, lengkap dengan sumber dan waktu koleksi. |
| collector_runs | Hasil tiap siklus collector atau marker PENDING dari dashboard. |
| reports | Metadata PDF serta lokasi file pada REPORTS_DIR. |
| revoked_tokens | Denylist jti sampai token kadaluarsa. |

Riwayat migrasi berada di alembic/versions. Gunakan Alembic, bukan
Base.metadata.create_all, untuk database aplikasi:

~~~bash
docker compose exec api alembic current
docker compose exec api alembic upgrade head
~~~

## Pengujian

Jalankan dari root proyek:

~~~bash
docker compose run --rm --no-deps --entrypoint python api -m pytest -q
~~~

Suite menggunakan PostgreSQL-independent SQLite in-memory dengan StaticPool,
mengganti dependency database FastAPI, dan membuat user/data fixture sendiri.
Ia menguji konfigurasi, autentikasi/revocation, user, logs, monitoring, report,
dan batas timezone tanpa mengubah database Compose.

Untuk menjalankan lokal setelah mengaktifkan virtual environment:

~~~bash
cd api
pytest -q
~~~

## Troubleshooting

| Gejala | Pemeriksaan |
|---|---|
| Container API berhenti saat startup | docker compose logs api; periksa DATABASE_URL, PostgreSQL, SEED_MODE, dan production safety check. |
| 401 setelah logout/refresh/reset password | Token lama memang revoke/invalid; login lagi dan gunakan token baru. |
| 403 pada endpoint | Pastikan role sesuai tabel endpoint; service dan collector bukan role dashboard. |
| 422 pada ingest | Validasi payload, status SUCCESS/FAILED, batas field, dan timestamp ber-offset. |
| PDF download mengembalikan 410 | File tidak lagi ada di REPORTS_DIR/volume reports meski metadata database masih ada. |
| CORS browser gagal | Tambahkan origin dashboard yang tepat ke CORS_ORIGINS, lalu rebuild/restart API. |

Untuk masalah yang melibatkan reporter atau collector, lihat README komponen
masing-masing agar konektivitas dan kredensial machine account dapat dicek dari
sumbernya.
