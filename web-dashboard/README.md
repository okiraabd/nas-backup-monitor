# Web Dashboard

Web Dashboard adalah React single-page application untuk operator dan admin NAS
Backup Monitor. Aplikasi membaca semua data melalui FastAPI; tidak ada koneksi
browser langsung ke PostgreSQL, NAS, Ceph, atau SNMP Exporter.

Di production, Vite membangun aset statis dan Nginx menyajikannya. Nginx juga
meneruskan request /api ke service FastAPI pada jaringan Compose.

~~~text
Browser ──► Nginx / React SPA
              │
              └── /api/* ──► FastAPI API ──► PostgreSQL
~~~

Untuk gambaran sistem dan cara menjalankan seluruh stack, lihat
[README root](../README.md). Kontrak backend ada di [README API](../api/README.md).

## Fitur dan route

| Route | Halaman | Akses UI |
|---|---|---|
| /login | Login akun API. | Public |
| /dashboard | Ringkasan backup, monitoring, failed logs, dan tren aktivitas. | Admin/operator; client menolak role machine sebelum menyimpan sesi. |
| /dashboard/logs | Daftar backup log dengan filter, pagination, auto refresh, dan hapus admin-only. | Admin/operator melalui API; hapus hanya admin. |
| /dashboard/logs/:id | Detail log, acknowledge FAILED, dan hapus admin-only. | Admin/operator melalui API; hapus hanya admin. |
| /dashboard/monitor/nas | Snapshot dan history metric NAS. | Admin/operator melalui API. |
| /dashboard/monitor/ceph | Snapshot dan history metric Ceph. | Admin/operator melalui API. |
| /dashboard/monitor/collector | Status run dan request Run once. | Admin/operator melalui API. |
| /dashboard/reports | Generate, download, pencarian, dan hapus report menurut role. | Admin/operator; hapus hanya admin. |
| /dashboard/users | Manajemen user dan rotasi machine account. | Admin. |

Sidebar menyembunyikan menu Users untuk non-admin. Otorisasi yang sebenarnya
tetap dilakukan server. Machine account service/collector dapat memperoleh
token API untuk ingest, tetapi web dashboard menolak login mereka dengan pesan
yang jelas dan endpoint dashboard tetap mengembalikan 403 sebagai pengaman.

Aksi destruktif hanya ditampilkan untuk admin. Backup log dapat dihapus per
item, pilihan banyak item, atau periode tanggal WIB yang dikonversi frontend ke
rentang UTC. Report dapat dihapus per item, pilihan banyak item, atau periode
tanggal generate; API menginterpretasikan periode report menurut APP_TIMEZONE.

### Pola refresh data

Dashboard overview, Backup Logs, NAS Monitoring, dan Ceph Monitoring memakai
auto-refresh 10 detik secara default. Kontrol desktop menyediakan pilihan Off,
10 detik, 30 detik, 1 menit, dan 5 menit serta tombol refresh manual. TanStack
Query tidak menjalankan interval saat tab browser berada di background kecuali
opsi background polling diaktifkan secara eksplisit.

Halaman Collector Status memeriksa status setiap 2 detik agar permintaan Run
once cepat terlihat. Endpoint history NAS/Ceph belum mengirim `max_points`
secara eksplisit, tetapi API terbaru menerapkan default 300 dan melakukan
sampling di database sebelum hasil dikirim ke grafik.

## Teknologi

- React 19 dan TypeScript.
- Vite untuk development/build.
- React Router untuk routing browser.
- TanStack Query untuk request, cache, dan invalidasi data.
- Axios dengan interceptor Authorization Bearer dan penanganan 401.
- Tailwind CSS, Radix UI, dan komponen gaya shadcn.
- Recharts untuk grafik metric/tren.
- Nginx Alpine untuk image production.

## Koneksi API

Client Axios memakai nilai berikut:

1. VITE_API_BASE_URL bila tersedia saat Vite build.
2. /api pada bundle production bila variabel tidak tersedia.
3. http://localhost:8000/api saat Vite development bila variabel tidak tersedia.

VITE_API_BASE_URL adalah variabel build-time, bukan runtime. Mengubahnya setelah
bundle dibuat tidak mengubah aplikasi yang sudah berjalan.

### Development lokal

Jika API lokal berada di http://localhost:8000, konfigurasi tambahan tidak
diperlukan. Bila alamat API berbeda, buat web-dashboard/.env.local:

~~~env
VITE_API_BASE_URL=http://localhost:8000/api
~~~

Atau ganti dengan alamat API development Anda. Vite membaca file env dari
direktori web-dashboard, bukan root proyek.

### Docker Compose

Dockerfile Compose saat ini tidak meneruskan VITE_API_BASE_URL sebagai build
argument. Ini disengaja karena bundle production memakai /api dan Nginx
mem-proxy path tersebut ke service api:

~~~nginx
location /api/ {
    proxy_pass http://api:8000/api/;
}
~~~

Dengan pola ini browser tidak perlu mengetahui hostname container api dan CORS
umumnya tidak terlibat untuk akses dashboard normal. Jangan menyetel
VITE_API_BASE_URL ke hostname Docker internal seperti http://api:8000/api:
hostname itu tidak dapat di-resolve oleh browser pengguna.

## Menjalankan untuk development

Prasyarat: Node.js yang kompatibel dengan image project (Node 20 atau lebih
baru) dan API yang dapat dijangkau.

~~~bash
cd web-dashboard
npm ci
npm run dev
~~~

Vite secara default melayani aplikasi pada http://localhost:5173. Konfigurasi
server mengizinkan host development apa pun agar dashboard dapat dibuka dari
host LAN; batasi exposure dengan firewall atau reverse proxy yang sesuai.

Perintah yang tersedia:

| Perintah | Fungsi |
|---|---|
| npm run dev | Menjalankan Vite dev server. |
| npm run build | Type-check dengan tsc lalu membangun bundle production ke dist/. |
| npm run lint | Menjalankan oxlint. |
| npm run preview | Menyajikan bundle dist secara lokal untuk verifikasi. |

Gunakan npm ci untuk instalasi reproducible karena package-lock.json tersedia.
Folder node_modules dan dist tidak perlu di-commit.

## Build dan container production

Build lokal:

~~~bash
cd web-dashboard
npm ci
npm run build
npm run preview
~~~

Build Compose:

~~~bash
cd ..
docker compose up -d --build web-dashboard
docker compose logs -f web-dashboard
~~~

Dockerfile memakai dua stage:

1. node:20-alpine memasang dependensi dan menjalankan npm run build.
2. nginx:alpine menyalin dist dan konfigurasi Nginx, lalu melayani port 80.

WEB_HOST_PORT pada root .env menentukan port host. Defaultnya membuat dashboard
tersedia di http://localhost. Untuk perubahan frontend, gunakan docker compose
up -d --build web-dashboard; docker compose restart tidak membangun bundle baru.

## State, autentikasi, dan waktu

### Autentikasi

Setelah login, access token JWT disimpan dalam localStorage dengan key token.
Setiap request Axios memasangnya sebagai header Authorization. Saat aplikasi
dibuka kembali, AuthProvider memanggil GET /api/auth/me untuk memvalidasi token.
Respons 401 pada request non-login menghapus token dan mengarahkan pengguna ke
/login.

Logout memanggil endpoint logout API jika memungkinkan, lalu menghapus token
lokal. Frontend saat ini tidak melakukan refresh token otomatis; pengguna perlu
login lagi ketika token kadaluarsa atau di-revoke.

Karena token ada di localStorage, deployment production harus mencegah XSS:
gunakan HTTPS, review konten pihak ketiga, batasi CSP melalui reverse proxy
sesuai kebijakan, dan jangan menyisipkan HTML tidak tepercaya.

### Waktu dan filter tanggal

Utilitas frontend secara eksplisit menggunakan Asia/Jakarta dengan label WIB.
Filter tanggal backup log diubah menjadi rentang UTC yang mencakup satu hari
WIB penuh. API sendiri menyimpan instant UTC serta menggunakan APP_TIMEZONE
untuk report/tren.

Pertahankan APP_TIMEZONE=Asia/Jakarta pada deployment saat ini. Mengubah API
ke zona lain akan membuat batas tanggal dashboard dan API tidak sejalan sampai
frontend dibuat configurable.

## Pengujian dan kualitas

Saat ini proyek dashboard menyediakan lint dan build/type-check, tetapi belum
memiliki test runner atau test unit/e2e frontend.

Sebelum handoff:

~~~bash
cd web-dashboard
npm ci
npm run lint
npm run build
~~~

Lakukan smoke test manual terhadap:

- login sebagai admin dan operator;
- penolakan login dashboard untuk akun service dan collector;
- redirect 401 serta logout;
- filter tanggal/log, acknowledge failure, dan pagination;
- halaman NAS, Ceph, serta status collector;
- auto-refresh, pilihan interval, refresh manual, dan penghentian polling saat
  tab browser berada di background;
- generate/download report;
- delete backup log/report sebagai admin, termasuk pilihan banyak item dan
  periode;
- pembatasan menu dan endpoint Users untuk non-admin;
- reload URL dalam (misalnya /dashboard/logs) untuk memastikan fallback Nginx
  mengembalikan index.html.

## Troubleshooting

| Gejala | Pemeriksaan |
|---|---|
| Browser meminta localhost:8000 yang salah | Periksa VITE_API_BASE_URL pada web-dashboard/.env.local dan restart Vite. |
| Production mendapat 404 saat membuka route dalam | Pastikan Nginx memakai try_files dengan fallback /index.html. |
| Production API gagal atau CORS error | Pastikan browser memanggil /api melalui Nginx; periksa service api dan konfigurasi proxy. |
| Login langsung kembali ke halaman login | Periksa response /api/auth/me, token localStorage, waktu sistem, dan JWT API. |
| Menu Users tidak terlihat | Hanya user berrole admin yang melihatnya. |
| Aksi ditolak 403 meski route terbuka | Server adalah sumber otorisasi; periksa role account dan endpoint API. |
| Perubahan UI tidak terlihat di Compose | Bangun ulang image web-dashboard, bukan sekadar restart container. |
