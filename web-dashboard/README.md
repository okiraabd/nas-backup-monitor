# Web Dashboard

Antarmuka web untuk **NAS Backup Monitor**. Aplikasi ini adalah SPA React yang
di-build oleh Vite dan disajikan oleh Nginx saat production.

## Fitur utama

- Overview backup dan monitoring.
- Backup logs dengan filter tanggal lokal WIB/`Asia/Jakarta`.
- Detail log dan acknowledge failed backup.
- Monitoring NAS dan Ceph.
- Collector status.
- Generate/download PDF reports.
- User management untuk admin.
- Dark mode.

## Stack

- React 19 + TypeScript
- Vite
- TailwindCSS
- Radix UI / shadcn-style components
- TanStack Query
- React Router
- Recharts
- Axios
- Nginx untuk production container

## Development

Jalankan dari folder `web-dashboard/`:

```bash
npm install
npm run dev
```

Dev server berjalan di `http://localhost:5173`.

API base URL dibaca dari `VITE_API_BASE_URL`. Pada setup Docker Compose, nilai
ini ada di root `.env` / `.env.example`. Untuk dev lokal, gunakan:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

## Build

```bash
npm run build
```

Output build berada di `dist/` dan tidak perlu dicommit.

## Docker

Production dashboard dijalankan lewat root Compose:

```bash
docker compose up -d --build web-dashboard
```

Container `bm_web` menyajikan bundle statis melalui Nginx di port `80`.
