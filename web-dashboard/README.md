# Web Dashboard (React + Vite)

Antarmuka pengguna (UI) modern untuk sistem **NAS Backup Monitor**. Dibangun menggunakan **React**, di-build super cepat dengan **Vite**, dan didesain secara elegan menggunakan **TailwindCSS** serta **shadcn/ui**.

## 🌟 Fitur Utama
- **Overview Dashboard**: Menampilkan metrik krusial seperti *Ceph Storage Health*, status perangkat NAS (Fresh/Stale/Offline), dan rasio kesuksesan pencadangan (*Backup Success Rate*).
- **Monitoring Detail**: Laman pemantauan metrik secara spesifik (CPU, Memory, Suhu, dll) lengkap dengan grafik (*charts*).
- **Backup Logs & Reports**: Fitur rekam jejak (*logs*) operasional pencadangan serta ekspor laporan akhir ke format PDF.
- **Dark Mode**: Mendukung peralihan mode Terang/Gelap (terintegrasi dengan preferensi sistem).
- **Docker Ready**: Aplikasi tidak perlu dijalankan dengan `npm run dev` di production. Repositori ini sudah memaketkan Web Dashboard menggunakan **Nginx** (via *multi-stage Docker build*) demi performa yang sangat ringan.

## 🛠️ Stack Teknologi
- **Core**: React 18, TypeScript, Vite
- **Styling**: TailwindCSS, class-variance-authority, lucide-react
- **Komponen**: shadcn/ui (Radix UI)
- **Routing & State**: React Router DOM, React Query (@tanstack/react-query)
- **Charts**: Recharts
- **Server (Production)**: Nginx (Alpine)

## 🚀 Panduan Menjalankan (Lokal / Development)

Meski di *production* dashboard ini disajikan melalui *Docker Compose* (lihat README root), Anda dapat menjalankannya secara independen untuk keperluan *development*:

### 1. Prasyarat
Pastikan **Node.js** (versi 18 atau 20) sudah terinstal.

### 2. Instalasi Dependensi
```bash
cd web-dashboard
npm install
```

### 3. Konfigurasi Environment
Salin file environment (pastikan variabel `VITE_API_URL` mengarah ke *backend API* Anda, misalnya `http://localhost:8000/api`):
```bash
cp .env.example .env
```

### 4. Mulai Development Server
```bash
npm run dev
```
Buka `http://localhost:5173` di browser Anda.

## 📦 Build untuk Production (Manual)
Jika Anda tidak menggunakan Docker dan ingin me-compile frontend secara manual:
```bash
npm run build
```
Hasil kompilasi (*bundle*) akan berada di dalam folder `dist/` dan siap disajikan (serve) menggunakan web server apapun (Nginx, Apache, dll).
