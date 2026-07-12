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
- Menyediakan operasi admin untuk pembersihan backup log/report dan manajemen
  akun.
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

Bagian ini menjelaskan mekanisme yang benar-benar dipakai kode, bukan sekadar
konsep JWT secara umum. API menggunakan access token JWT bertipe Bearer yang
ditandatangani secara simetris. Tidak ada refresh token terpisah, cookie sesi,
atau session server-side untuk autentikasi normal.

~~~text
Authorization: Bearer ACCESS_TOKEN
~~~

Semua endpoint di bawah /api kecuali POST /api/auth/login membutuhkan token.
Endpoint /health berada di luar prefix /api dan juga public.

### Gambaran alur

~~~text
1. Client ── username + password ──► POST /api/auth/login
                                      │
                                      ├─ cari user, bcrypt verify, cek aktif
                                      ├─ update last_login_at
                                      └─ buat JWT bertanda tangan
                                               │
2. Client ◄── access_token + user ───────────┘
   menyimpan token dan mengirimkannya sebagai Authorization: Bearer ...
                                               │
3. Request protected ───────────────────────► API dependency
                                      │
                                      ├─ verifikasi signature + claim JWT
                                      ├─ cek jti tidak ada di revoked_tokens
                                      ├─ muat user terbaru dari database
                                      ├─ cek user aktif
                                      ├─ cek token version
                                      └─ cek role endpoint dari user database
                                               │
4. API ◄─────────────────────────────────────┘ respons atau 401/403
~~~

JWT membuktikan bahwa token diterbitkan API dan belum kadaluarsa. Database
tetap ikut terlibat di setiap endpoint protected untuk memeriksa revocation,
status akun, token version, dan role terkini. Jadi implementasi ini bukan JWT
yang sepenuhnya stateless.

### Login dan penerbitan token

POST /api/auth/login menerima username dan password dalam JSON. API:

1. Mencari username pada tabel users.
2. Memverifikasi password terhadap password_hash menggunakan bcrypt.
3. Menolak user yang tidak ada atau password salah dengan 401.
4. Menolak user nonaktif dengan 403.
5. Memperbarui last_login_at.
6. Membuat JWT baru dengan masa berlaku ACCESS_TOKEN_EXPIRE_MINUTES.
7. Mengembalikan access_token, token_type bearer, dan profil user tanpa hash
   password.

Password plaintext hanya dipakai pada proses login atau reset. API tidak
menyimpan password plaintext dan tidak pernah mengembalikan hash password.

### Isi token

Token dibuat oleh app.security.create_access_token. Claim yang terkandung:

| Claim | Contoh arti | Dipakai untuk |
|---|---|---|
| sub | username | Subject/identitas username token. |
| uid | ID user internal | Mengambil user dari database pada request berikutnya. |
| role | admin, operator, service, atau collector | Informasi token/audit; otorisasi runtime memakai role terbaru dari database. |
| tv | token_version user saat token dibuat | Invalidasi seluruh token lama milik satu user. |
| jti | ID token acak unik | Denylist/revocation untuk satu token tertentu. |
| iss | JWT_ISSUER | Memastikan token berasal dari issuer aplikasi yang benar. |
| aud | JWT_AUDIENCE | Memastikan token ditujukan untuk client API ini. |
| iat | waktu token dibuat | Claim wajib yang diverifikasi keberadaannya. |
| nbf | waktu token mulai berlaku | Token belum dapat dipakai sebelum waktu ini. |
| exp | waktu token kadaluarsa | Token tidak dapat dipakai sesudah waktu ini. |

Waktu claim JWT memakai UTC. Signature dibuat dengan JWT_SECRET_KEY dan
JWT_ALGORITHM; default algoritma adalah HS256. Mengubah JWT_SECRET_KEY
mengakibatkan semua token yang dibuat dengan secret lama tidak dapat
diverifikasi lagi dan pengguna harus login ulang.

Role memang ada di dalam JWT, tetapi API tidak mempercayai claim role itu
sebagai sumber keputusan akhir. Setelah token lolos validasi, API membaca baris
User dari database dan require_roles membandingkan current_user.role. Akibatnya,
perubahan role pada database langsung memengaruhi izin request berikutnya,
bahkan bila token lama masih memiliki claim role sebelumnya.

### Urutan validasi request protected

Dependency get_current_user menjalankan pemeriksaan berikut secara berurutan:

1. HTTPBearer mengambil kredensial dari header Authorization. Header kosong,
   token kosong, atau skema tidak ada menghasilkan 401 Not authenticated.
2. decode_access_token memverifikasi signature, algoritma, exp, nbf, iss, dan
   aud menggunakan PyJWT. Claim exp, iat, dan sub wajib ada. Token rusak,
   salah secret, salah issuer/audience, belum berlaku, atau expired
   menghasilkan 401 Invalid or expired token.
3. API mencari jti pada revoked_tokens. Bila ditemukan, token itu sudah
   logout/dirotasi dan menghasilkan 401 Token has been revoked.
4. API mengambil user berdasarkan uid. User yang tidak ditemukan menghasilkan
   401 User not found.
5. API memeriksa is_active. User nonaktif menghasilkan 403 User is inactive.
6. API membandingkan tv pada token dengan user.token_version terkini. Nilai
   berbeda menghasilkan 401 dan client harus login kembali.
7. Endpoint dengan require_roles memeriksa role terbaru pada user database.
   Role yang tidak sesuai menghasilkan 403.

Pemeriksaan jti dan token_version membuat token valid secara kriptografis tetap
dapat ditolak sebelum exp, misalnya ketika user logout atau password di-reset.

### Logout, refresh, dan dua tingkat revocation

JWT biasa bersifat self-contained sehingga logout normal hanya dapat menghapus
token di client. API ini menambahkan penyimpanan revoke di database agar logout
berlaku segera.

#### Logout satu token

POST /api/auth/logout menerima token yang masih valid secara kriptografis. API
mengambil jti dan exp, lalu memasukkan jti ke tabel revoked_tokens dengan
expires_at sama dengan exp token. Request berikutnya yang memakai token itu
ditolak 401, sementara token lain dari user yang sama tetap dapat digunakan.

Logout bersifat per-sesi/per-token, bukan logout semua perangkat. Client tetap
harus menghapus token lokalnya setelah respons logout.

Sebelum menambah revoke baru, API menghapus record revoked_tokens yang sudah
melewati expires_at. Pembersihan ini bersifat lazy: ia terjadi saat logout atau
refresh, bukan melalui scheduled job. Record yang baru selesai kadaluarsa tidak
menimbulkan risiko karena tokennya sendiri sudah ditolak berdasarkan exp.

#### Refresh adalah rotasi access token

POST /api/auth/refresh bukan mekanisme refresh-token klasik. Endpoint ini
mengharuskan access token yang sedang berlaku, tidak revoke, user aktif, dan
token version-nya masih cocok. Setelah itu API:

1. Menyimpan jti token yang dipresentasikan ke denylist.
2. Membuat access token baru dengan jti dan exp baru.
3. Mengembalikan token baru serta profil user.

Dengan demikian, token lama tidak dapat digunakan ulang setelah refresh.
Dashboard saat ini tidak memanggil refresh otomatis; pengguna login kembali
ketika token habis atau API mengembalikan 401. Collector mendapat token baru
dengan login pada siklus berikutnya ketika diperlukan. Tidak ada endpoint
refresh token jangka panjang.

#### Invalidasi seluruh token satu user

Setiap user memiliki kolom integer token_version. Nilai itu dimasukkan sebagai
tv ketika token diterbitkan. API menginvalidasi semua token aktif user dengan
menaikkan token_version pada operasi berikut:

| Operasi | Dampak |
|---|---|
| PATCH /api/users/{id}/password | Password diubah dan seluruh token user menjadi tidak valid. |
| POST /api/users/{id}/rotate-token | Password baru untuk service/collector dibuat; seluruh token lama invalid. |
| PATCH /api/users/{id} dengan is_active=false | User dinonaktifkan dan seluruh token lama invalid. |
| DELETE /api/users/{id} | User dihapus permanen bila tidak punya data terkait, atau dinonaktifkan dan token lama invalid bila data historis perlu dipertahankan. |

Tidak ada endpoint khusus logout everywhere. Admin dapat memakai reset password
atau rotate-token untuk machine account bila perlu memutus seluruh sesi user.

Mengubah role tidak menaikkan token_version. Ini tetap aman untuk otorisasi
karena setiap request mengambil role terbaru dari database; role baru langsung
dipakai untuk allow/deny endpoint. Namun token masih dapat melewati validasi
identitas sampai kadaluarsa, logout, atau invalidasi lain terjadi.

### RBAC dan akun manusia vs machine account

| Role | Hak utama |
|---|---|
| admin | Seluruh endpoint dashboard, report, dan manajemen user. |
| operator | Membaca data, acknowledge kegagalan, membuat/mengunduh report, meminta collector run. |
| service | Mengirim backup log dari NAS. |
| collector | Mengirim metric dan hasil collector run; membaca status collector. |

Semua account aktif dapat memperoleh JWT dan memanggil GET /api/auth/me. Hanya
admin/operator yang dapat memakai data dashboard. Account service dan collector
sebaiknya bersifat machine-only serta dipisahkan per integrasi untuk audit dan
rotasi secret yang aman.

### Status error autentikasi

| Situasi | Status | Makna untuk client |
|---|---:|---|
| Username tidak ada atau password salah saat login | 401 | Jangan mengungkap user mana yang salah; minta kredensial benar. |
| User nonaktif saat login/request | 403 | Account harus diaktifkan admin sebelum dipakai lagi. |
| Header Bearer tidak ada | 401 | Login atau sertakan token. |
| Token rusak, expired, salah signature/issuer/audience, atau belum berlaku | 401 | Buang token lama dan login ulang. |
| jti ada pada revoked_tokens | 401 | Token sudah logout atau telah dirotasi; gunakan token baru. |
| tv token berbeda dengan token_version database | 401 | Semua token user telah diinvalidasi; login ulang. |
| Role tidak memiliki izin endpoint | 403 | Gunakan account/role yang sesuai; login ulang saja tidak menaikkan privilege. |

### Panduan operasional dan hardening

- Production wajib memakai APP_ENV=production, JWT_SECRET_KEY acak kuat
  minimal 32 karakter, dan SEED_MODE=none setelah bootstrap.
- Distribusikan API melalui HTTPS. Bearer token dapat digunakan oleh siapa pun
  yang memilikinya sampai expired atau direvoke.
- Jangan mengirim token pada URL, query string, log aplikasi, atau chat.
- Gunakan masa hidup token yang sesuai risiko. Masa hidup lebih singkat
  membatasi dampak token bocor, tetapi membutuhkan login/refresh lebih sering.
- Simpan password service/collector di secret store atau file berizin ketat,
  bukan di repository.
- Rotasi password machine account lewat endpoint rotate-token, simpan password
  baru sekali tampil, lalu perbarui NAS/collector sebelum proses lama berhenti.
- Ubah JWT_SECRET_KEY secara terencana bila terjadi insiden global; tindakan
  ini memutus seluruh sesi dan memerlukan restart/redeploy API.
- CORS_ORIGINS membatasi origin browser, tetapi bukan pengganti autentikasi dan
  bukan kontrol akses untuk client non-browser.

Mekanisme yang belum disediakan oleh kode saat ini meliputi rate limiting
login, account lockout, MFA, cookie HttpOnly/SameSite, dan audit trail khusus
per peristiwa autentikasi. Letakkan rate limiting/WAF dan TLS pada reverse
proxy bila deployment membutuhkan kontrol tersebut.

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
| DELETE /api/logs/bulk | admin | Menghapus permanen log berdasarkan ID, periode, atau gabungan keduanya. |

POST /api/logs/ingest mengembalikan 201 untuk snapshot baru dan 200 untuk retry
snapshot yang sudah tersimpan. Idempotensi berlaku hanya ketika snapshot_id
ada, berdasarkan kombinasi nas_id, job_name, dan snapshot_id. Failure tanpa
snapshot_id sengaja dicatat sebagai event terpisah.

GET /api/logs menerima filter nas_id, status, job_name, date_from, date_to,
acknowledged, page, dan page_size. page_size berada pada rentang 1 sampai 100.
Hanya log berstatus FAILED yang dapat di-acknowledge.

DELETE /api/logs/bulk menerima body log_ids, date_from, dan/atau date_to.
Minimal satu filter wajib ada. Jika ID dan periode dikirim bersamaan, API
menghapus log yang cocok dengan salah satu kondisi tersebut. date_from dan
date_to adalah datetime UTC; dashboard mengubah input tanggal WIB menjadi
rentang UTC sebelum memanggil endpoint ini. Operasi ini permanen dan tidak
menghapus file PDF report yang sudah pernah dibuat dari log tersebut.

### Monitoring dan collector

| Method dan path | Role | Keterangan |
|---|---|---|
| POST /api/monitor/ingest | collector | Menyimpan batch metric NAS atau Ceph. |
| GET /api/monitor/summary | admin, operator | Jumlah NAS dan ringkasan Ceph. |
| GET /api/monitor/activity-trend | admin, operator | Tren log SUCCESS/FAILED tujuh hari kalender lokal terakhir. |
| GET /api/monitor/nas | admin, operator | Snapshot metric terbaru semua NAS. |
| GET /api/monitor/nas/{nas_id} | admin, operator | Snapshot terbaru satu NAS. |
| GET /api/monitor/nas/{nas_id}/history | admin, operator | History satu metric NAS; parameter metric, limit, hours, date_from, dan date_to. |
| GET /api/monitor/ceph | admin, operator | Snapshot terbaru Ceph. |
| GET /api/monitor/ceph/history | admin, operator | History metric Ceph; metric, limit, hours, date_from, date_to, dan source_id opsional. |
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
| DELETE /api/reports | admin | Bulk delete report berdasarkan ID, tanggal generate, atau gabungan keduanya. |
| GET /api/users | admin | Daftar user aktif; include_inactive=true menampilkan user nonaktif. |
| POST /api/users | admin | Membuat user. |
| GET /api/users/{user_id} | admin | Detail user. |
| PATCH /api/users/{user_id} | admin | Ubah display name, role, atau aktif/nonaktif. |
| DELETE /api/users/{user_id} | admin | Smart delete; hard-delete bila aman, soft-delete bila ada data terkait, force=true untuk hard-delete dengan FK dibuat NULL. |
| PATCH /api/users/{user_id}/password | admin | Set password baru dan invalidate token lama. |
| POST /api/users/{user_id}/rotate-token | admin | Buat password baru sekali tampil untuk role service/collector. |

API melindungi dari hilangnya akses admin terakhir dan mencegah admin
menonaktifkan/menghapus akses adminnya sendiri. Hapus report bulk menerima
report_ids, date_from, dan/atau date_to; tanggal periode diinterpretasikan
sebagai hari lokal menurut APP_TIMEZONE. Hapus user bersifat hard-delete hanya
bila tidak ada log, metric, atau report yang mereferensikan user tersebut.
Tanpa force=true, user yang memiliki data historis akan dinonaktifkan agar
riwayat tetap utuh.

## Kontrak waktu dan data

Semua timestamp masuk harus menyertakan offset zona waktu:

~~~text
2026-07-10T09:00:00+07:00
2026-07-10T02:00:00Z
~~~

Timestamp disimpan sebagai instant UTC. Untuk request report, date_from dan
date_to adalah tanggal tanpa waktu dan meliputi satu hari penuh menurut
APP_TIMEZONE. Filter log dan bulk delete log menerima timestamp. Bulk delete
report memakai tanggal lokal seperti request report. PDF report memuat:

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
