# NAS & Ceph Backup Monitor

NAS & Ceph Backup Monitor adalah sistem internal untuk melihat hasil backup
Kopia dari NAS, kesehatan NAS, dan kondisi Ceph Object Storage dari satu
dashboard. Sistem ini dibuat untuk lingkungan KKP PT Lucky Mom Indonesia.

Proyek ini adalah sistem observabilitas dan pelaporan, bukan mesin backup:

- Kopia tetap menangani policy, jadwal, retention, dan upload snapshot.
- NAS reporter hanya membaca hasil snapshot Kopia dan mengirimkannya ke API.
- Collector hanya membaca metrik dari SNMP Exporter dan endpoint Prometheus
  Ceph.
- PostgreSQL hanya diakses oleh komponen backend tepercaya: API dan worker
  `metric-cleanup`. Browser, reporter, dan collector selalu memakai API.

## Daftar isi

- [Arsitektur dan aliran data](#arsitektur-dan-aliran-data)
- [Komponen](#komponen)
- [Mulai cepat dengan Docker Compose](#mulai-cepat-dengan-docker-compose)
- [Akun awal dan peran](#akun-awal-dan-peran)
- [Konfigurasi](#konfigurasi)
- [Deployment monitoring nyata](#deployment-monitoring-nyata)
- [Operasional](#operasional)
- [Pengembangan dan pengujian](#pengembangan-dan-pengujian)
- [Batasan penting](#batasan-penting)
- [Dokumentasi per komponen](#dokumentasi-per-komponen)

## Arsitektur dan aliran data

~~~text
                      Browser
                         │ HTTPS / HTTP
                         ▼
                 Web Dashboard (Nginx)
                         │ /api reverse proxy
                         ▼
NAS Kopia Reporter ───► FastAPI API ◄─── Metric Collector
 POST /logs/ingest          │              POST /monitor/*
                             ▼
                        PostgreSQL
                             │
                             ▼
                     PDF report volume

NAS SNMP ── UDP/161 ──► SNMP Exporter ── HTTP /snmp ──► Metric Collector
Ceph mgr Prometheus ─────────────────── HTTP /metrics ─► Metric Collector
~~~

Empat proses utama bekerja secara independen:

1. Reporter pada setiap NAS menjalankan pembacaan Kopia berkala. Snapshot baru
   menjadi backup log; gangguan sebelum snapshot terbentuk juga dikirim sebagai
   event FAILED.
2. Collector berjalan terus-menerus. Ia mengumpulkan metrik NAS dan Ceph pada
   setiap interval, lalu mencatat hasil siklusnya.
3. Client web dan mobile menggunakan API berautentikasi untuk menampilkan
   status, mengulas kegagalan, mengelola data sesuai role, dan membuat PDF
   report.
4. Worker `metric-cleanup` memakai model/database API untuk menghapus metrik
   yang melewati masa retensi dalam batch, tanpa mengekspos endpoint baru.

Aplikasi mobile pada repo terpisah `nas-backup-monitor-mobile` juga berkomunikasi
langsung dengan FastAPI melalui HTTPS/HTTP; ia tidak memakai Nginx dashboard dan
tidak mengakses PostgreSQL atau target monitoring.

Semua instant waktu disimpan sebagai UTC. API menginterpretasikan periode
laporan menurut APP_TIMEZONE. Dashboard saat ini secara eksplisit menampilkan
WIB (Asia/Jakarta); lihat [Batasan penting](#batasan-penting).

## Komponen

| Lokasi | Tanggung jawab |
|---|---|
| [api](api/README.md) | FastAPI, JWT/RBAC, PostgreSQL, migrasi Alembic, log backup, metrik, PDF report, dan worker retensi metrik. |
| [web-dashboard](web-dashboard/README.md) | React SPA untuk operator dan admin, disajikan oleh Nginx di production. |
| nas-backup-monitor-mobile (repo terpisah) | Client Expo/Android untuk admin dan operator; collector tidak ditampilkan di mobile. |
| [collector](collector/README.md) | Daemon Python yang mengubah output SNMP Exporter dan Ceph Prometheus menjadi metrik dashboard. |
| [nas-scripts](nas-scripts/README.md) | Reporter aman di NAS untuk merekonsiliasi snapshot Kopia dan mengirim backup log. |
| [snmp-exporter](snmp-exporter/README.md) | Template module SNMP Exporter untuk Synology dan WD PR4100. |
| [snmp-exporter/mibs](snmp-exporter/mibs/README.md) | Panduan penyimpanan MIB vendor saat menghasilkan konfigurasi exporter. |
| docker-compose.yml | Stack lokal/mandiri: PostgreSQL, API, metric cleanup, dashboard, collector, dan profile SNMP Exporter opsional. |

## Mulai cepat dengan Docker Compose

### Prasyarat

- Docker Engine dan Docker Compose plugin.
- Port host yang tersedia: 80 untuk dashboard, 8000 untuk API, dan 5433 untuk
  PostgreSQL secara default.
- Untuk demo, tidak diperlukan NAS, Ceph, atau SNMP Exporter karena collector
  dapat memakai metrik acak.

### 1. Siapkan konfigurasi demo

Jalankan dari root proyek:

~~~bash
cp .env.example .env
~~~

Edit .env sebelum menyalakan stack. Template sengaja berisi placeholder
database dan collector. Untuk demo yang langsung dapat mengirim metrik, gunakan
akun collector seed berikut:

~~~env
APP_ENV=development
SEED_MODE=demo
USE_MOCK_METRICS=true
COLLECTOR_USERNAME=collector
COLLECTOR_PASSWORD=collector123
~~~

Pastikan DATABASE_URL konsisten dengan POSTGRES_USER, POSTGRES_PASSWORD, dan
POSTGRES_DB pada file yang sama. Jangan gunakan password contoh ini di
environment selain demo.

### 2. Validasi dan jalankan

~~~bash
docker compose config
docker compose up -d --build
docker compose ps
curl http://localhost:8000/health
~~~

Layanan default:

| Layanan | Alamat default | Keterangan |
|---|---|---|
| Dashboard | http://localhost | React SPA melalui Nginx. |
| API | http://localhost:8000 | FastAPI untuk seluruh client. |
| OpenAPI / Swagger | http://localhost:8000/docs | Kontrak API interaktif. |
| Liveness API | http://localhost:8000/health | Probe tanpa autentikasi. |
| PostgreSQL | localhost:5433 | Port host untuk administrasi; client aplikasi tidak memakainya. |
| Collector | tidak membuka port | Mengirim metrik ke API setiap siklus. |
| Metric cleanup | tidak membuka port | Menghapus metrik kedaluwarsa secara periodik. |

Startup API menunggu PostgreSQL, menjalankan seluruh migrasi Alembic, kemudian
menjalankan seed sesuai `SEED_MODE`. Collector dan `metric-cleanup` baru dimulai
setelah health check API berhasil. Gunakan log berikut bila sebuah service belum
siap:

~~~bash
docker compose logs -f api
docker compose logs -f collector
docker compose logs -f metric-cleanup
~~~

## Akun awal dan peran

SEED_MODE=users dan SEED_MODE=demo membuat akun berikut bila belum ada. Seed
bersifat idempoten; menjalankannya lagi tidak menggandakan data.

| Username | Password demo | Peran | Tujuan |
|---|---|---|---|
| admin | admin123 | admin | Administrasi penuh dan dashboard. |
| operator | operator | operator | Operasional dashboard, review kegagalan, dan report. |
| nas-synology | synology123 | service | Machine account reporter Synology. |
| nas-wd | wd123 | service | Machine account reporter WD. |
| collector | collector123 | collector | Machine account metric collector. |

Segera setelah bootstrap production:

1. Ubah atau rotasi semua password seed.
2. Nonaktifkan akun yang tidak dipakai.
3. Ganti SEED_MODE menjadi none.
4. Simpan kredensial machine account di secret store atau file dengan izin ketat.

Peran menentukan otorisasi API, bukan hanya menu dashboard.

| Kemampuan | Admin | Operator | Service | Collector |
|---|:---:|:---:|:---:|:---:|
| Mendapatkan JWT / melihat profil sendiri | ✓ | ✓ | ✓ | ✓ |
| Membaca dashboard, log, dan monitoring | ✓ | ✓ | – | – |
| Acknowledge backup FAILED | ✓ | ✓ | – | – |
| Membuat / mengunduh report | ✓ | ✓ | – | – |
| Menghapus backup log/report dan mengelola user | ✓ | – | – | – |
| Mengirim backup log | – | – | ✓ | – |
| Mengirim metrik dan hasil run collector | – | – | – | ✓ |
| Membaca status collector | ✓ | ✓ | – | ✓ |

Machine account secara teknis dapat login untuk memperoleh token, tetapi tidak
memiliki akses data dashboard. Jangan gunakan akun service atau collector untuk
pengguna manusia.

## Konfigurasi

Seluruh variabel Compose berada di .env. File itu tidak boleh di-commit.
Nilai bertanda production harus diputuskan sebelum deployment.

### Aplikasi, database, dan keamanan

| Variabel | Default Compose | Keterangan |
|---|---:|---|
| APP_ENV | development | Gunakan production untuk mengaktifkan validasi keamanan API. |
| APP_TIMEZONE | Asia/Jakarta | Zona IANA untuk batas tanggal API/report. Dashboard saat ini mengasumsikan nilai ini. |
| POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB | backup_monitor / backup_monitor_pw / backup_monitor | Kredensial database container. |
| DATABASE_URL | koneksi ke service postgres | URL SQLAlchemy API; harus sejalan dengan kredensial PostgreSQL. |
| POSTGRES_HOST_PORT | 5433 | Port host opsional untuk administrasi database. |
| JWT_SECRET_KEY | dev-secret-change-me | Wajib secret acak kuat, minimal 32 karakter, di production. |
| JWT_ALGORITHM | HS256 | Algoritma penandatanganan JWT. |
| ACCESS_TOKEN_EXPIRE_MINUTES | 60 | Masa hidup access token. |
| JWT_ISSUER / JWT_AUDIENCE | backup-monitor-api / backup-monitor-clients | Claim yang divalidasi ketika token dibaca. |
| CORS_ORIGINS | localhost origins | Origin browser yang diizinkan API. |
| SEED_MODE | none | none, users, atau demo. |
| REPORTS_DIR | /app/generated_reports | Lokasi report di container API; dipetakan ke volume reports. |
| METRIC_RETENTION_DAYS | 30 | Umur maksimum metric history. |
| METRIC_CLEANUP_INTERVAL_SECONDS | 3600 | Jeda antar cleanup metric. |
| METRIC_CLEANUP_BATCH_SIZE | 10000 | Batas penghapusan per transaksi. |

API menolak startup production bila SEED_MODE=demo, AUTO_SEED=true legacy, atau
JWT_SECRET_KEY masih lemah/default. APP_ENV=prod juga diperlakukan sebagai
production.

API_HOST dan API_PORT digunakan oleh proses API lokal. Pada Compose, API selalu
berjalan pada 0.0.0.0:8000 di dalam jaringan container; API_HOST_PORT hanya
mengubah pemetaan port host.

### Dashboard

| Variabel | Keterangan |
|---|---|
| WEB_HOST_PORT | Pemetaan port host ke Nginx port 80; default 80. |
| VITE_API_BASE_URL | Hanya untuk build/dev Vite. Tidak diteruskan sebagai build argument oleh Compose saat ini. |

Pada image Compose, VITE_API_BASE_URL tidak diisi sehingga bundle production
memakai /api. Nginx meneruskan path itu ke service API. Untuk Vite lokal,
default juga adalah http://localhost:8000/api; buat
web-dashboard/.env.local bila API lokal memakai alamat lain.

### Collector dan target monitoring

| Variabel | Keterangan |
|---|---|
| COLLECTOR_USERNAME / COLLECTOR_PASSWORD | Kredensial akun berperan collector. Harus sama dengan akun aktif pada API. |
| COLLECTOR_INTERVAL_SECONDS | Jeda setelah satu siklus collector selesai, default 10 detik. |
| USE_MOCK_METRICS | true menghasilkan metrik demo tanpa menghubungi NAS/Ceph. |
| SNMP_EXPORTER_URL | Endpoint centralized /snmp. Kosong berarti mode exporter legacy per target. |
| SNMP_DEFAULT_MODULE | Module fallback apabila target tidak menyebutkan module. |
| NAS_TARGETS | Daftar target dipisahkan koma; format lengkap dijelaskan di README collector. |
| CEPH_METRICS_URL | Endpoint Prometheus Ceph manager. |
| SNMP_EXPORTER_IMAGE | Image service exporter opsional; pin versi/digest saat production. |
| SNMP_EXPORTER_HOST_BIND / SNMP_EXPORTER_HOST_PORT | Bind host untuk exporter Compose; default 127.0.0.1:9116. |

## Deployment monitoring nyata

### NAS dan SNMP Exporter

Untuk production, tempatkan SNMP Exporter pada host yang dapat menjangkau NAS
melalui UDP/161. NAS hanya perlu mengizinkan UDP/161 dari host exporter, bukan
dari collector atau jaringan luas.

~~~text
NAS target                  SNMP Exporter host              Collector
192.168.24.5 ── UDP/161 ──► /snmp?target=...&module=... ──► HTTP
~~~

Gunakan module synology_nas untuk Synology dan wd_pr4100 untuk WD PR4100.
Panduan pembuatan dan pengujian konfigurasi ada di
[README SNMP Exporter](snmp-exporter/README.md).

Untuk memakai service exporter bawaan proyek:

~~~bash
cp snmp-exporter/snmp.yml.example snmp-exporter/snmp.yml
# Ganti community public dengan secret environment Anda bila diperlukan.
docker compose --profile snmp up -d snmp-exporter collector
~~~

Konfigurasi minimum collector nyata:

~~~env
USE_MOCK_METRICS=false
SNMP_EXPORTER_URL=http://snmp-exporter:9116/snmp?auth=kkp_snmp_v2
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100
CEPH_METRICS_URL=http://192.168.24.6:9283/metrics
~~~

### Reporter Kopia pada NAS

Instal reporter ke path persistent di setiap NAS, misalnya
/opt/nas-backup-monitor. Reporter memakai Docker CLI untuk membaca container
Kopia, menyimpan antrean lokal, dan mengirim log melalui HTTPS/HTTP API.
Kopia tetap merupakan pemilik jadwal backup.

Ikuti [README NAS reporter](nas-scripts/README.md) untuk instalasi, permission,
cron, dan perilaku retry queue.

## Operasional

### Pemeriksaan rutin

~~~bash
docker compose ps
docker compose exec api alembic current
curl http://localhost:8000/health
docker compose logs --tail=100 collector
docker compose logs --tail=100 metric-cleanup
~~~

Hal yang perlu diperiksa pada dashboard:

- backup FAILED yang belum di-acknowledge;
- status NAS fresh, stale, atau offline;
- ceph_reachable, health_status, dan kapasitas Ceph;
- status run collector terakhir dan apakah is_mock bernilai false di production.

Freshness ditentukan API, bukan browser: fresh hingga 90 detik, stale hingga
300 detik, lalu offline. Nilai ini saat ini bersifat konstan di kode.

### Data persisten dan backup

Compose menyimpan data pada dua named volume:

| Volume | Isi |
|---|---|
| pgdata | User, backup log, metric history, metadata report, dan token revoke. |
| reports | File PDF report yang dibuat API. |

Cadangkan PostgreSQL secara teratur dengan mekanisme PostgreSQL yang sesuai
dengan kebijakan organisasi, dan cadangkan volume reports jika PDF harus
dipertahankan. Uji proses restore pada lingkungan terpisah. Jangan gunakan
docker compose down -v kecuali memang ingin menghapus kedua volume tersebut.

Metric history tidak disimpan tanpa batas. Worker `metric-cleanup` menghapus
baris yang lebih tua dari `METRIC_RETENTION_DAYS` (default 30 hari), dimulai saat
worker start lalu diulang setiap `METRIC_CLEANUP_INTERVAL_SECONDS`.

Admin dapat menghapus backup log dan report melalui dashboard/API, baik per
item, pilihan banyak item, maupun periode. Operasi itu permanen pada database
dan, untuk report, juga mencoba menghapus file PDF terkait. Ambil backup sebelum
melakukan pembersihan massal pada data production.

### Upgrade

~~~bash
docker compose pull
docker compose up -d --build
docker compose exec api alembic current
~~~

Entrypoint API menjalankan alembic upgrade head saat startup. Tetap ambil backup
database sebelum upgrade production dan review migrasi di api/alembic/versions.

## Pengembangan dan pengujian

Perintah berikut dijalankan dari root proyek.

| Area | Perintah |
|---|---|
| API | docker compose run --rm --no-deps --entrypoint python api -m pytest -q |
| Collector | docker compose run --rm --no-deps --entrypoint python collector -m unittest discover -s tests -v |
| Dashboard lint | cd web-dashboard && npm ci && npm run lint |
| Dashboard build | cd web-dashboard && npm ci && npm run build |
| Reporter NAS | Lihat perintah container test pada README NAS reporter. |

Test API memakai SQLite in-memory dan tidak memerlukan PostgreSQL, termasuk test
sampling history serta batch retention. Test collector dan reporter menguji
parser/normalisasi dengan fixture serta mock; keduanya tidak menghubungi
perangkat nyata.

Untuk mengembangkan service tertentu, lihat README di direktori komponen.
Setelah perubahan Dockerfile atau kode service, gunakan docker compose up -d
--build NAMA_SERVICE; restart saja tidak membangun image baru.

## Batasan penting

- Service `metric-cleanup` menghapus metrik lebih tua dari `METRIC_RETENTION_DAYS`
  dalam batch. Default retensi adalah 30 hari, interval cleanup satu jam, dan
  batch 10000 baris. Pantau ukuran database dan sesuaikan nilainya dengan
  jumlah sumber serta cadence collector.
- History rentang waktu dibatasi lewat `max_points` (default 300) dengan sampling
  merata agar respons grafik tetap terkontrol. Data mentah tetap tersimpan sampai
  melewati masa retensi.
- Jika SNMP atau Ceph tidak dapat diakses, collector tetap mengirim metrik
  fallback dengan reachability 0 bila API dapat dijangkau. Periksa metrik
  reachability, bukan hanya status proses collector.
- Tombol Run once pada dashboard mencatat permintaan PENDING. Collector daemon
  yang mendeteksinya pada polling berikutnya yang benar-benar menjalankan
  pengambilan data.
- API mendukung APP_TIMEZONE IANA apa pun yang valid, tetapi dashboard saat ini
  mengformat dan membentuk filter tanggal sebagai Asia/Jakarta/WIB. Pertahankan
  APP_TIMEZONE=Asia/Jakarta sampai frontend dibuat timezone-aware.
- Aplikasi tidak mengirim alert e-mail, chat, atau paging. Dashboard dan API
  menyediakan data yang dapat diintegrasikan ke mekanisme alert eksternal.

## Dokumentasi per komponen

- [API: endpoint, RBAC, migrasi, dan PDF report](api/README.md)
- [Web dashboard: development, build, routing, dan koneksi API](web-dashboard/README.md)
- [Metric collector: mode mock/real dan normalisasi metrik](collector/README.md)
- [Kopia NAS reporter: instalasi, antrean, dan cron](nas-scripts/README.md)
- [SNMP Exporter: module, generator, dan hardening jaringan](snmp-exporter/README.md)
- [MIB vendor: struktur dan sumber file](snmp-exporter/mibs/README.md)

## Lisensi dan konteks

Proyek ini dikembangkan untuk kebutuhan internal KKP PT Lucky Mom Indonesia.
Tidak ada lisensi open-source yang dinyatakan dalam repositori ini.
