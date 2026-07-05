# Metric Collector Daemon

Ini adalah layanan latar belakang (*standalone daemon*) berwujud *script Python* yang bertugas mengumpulkan metrik telemetri dari perangkat keras NAS dan sistem penyimpanan Ceph.

Collector ini bertugas untuk menyuntikkan (POST) berbagai metrik tersebut secara berkala ke sentral REST API kita (`/api/monitor/ingest`).

## 🛠️ Stack Teknologi
- **Bahasa**: Python 3.12
- **Dependensi Utama**: `requests` (untuk komunikasi HTTP ke API), `python-dotenv`.

## ⚙️ Cara Kerja
Saat daemon dinyalakan, sistem akan terus melakukan putaran (*loop*) setiap `COLLECTOR_INTERVAL_SECONDS` (contoh: setiap 60 detik). Pada setiap siklus, ia akan:
1. Mengambil metrik (CPU, RAM, Suhu, Kapasitas) dari entitas yang dipantau.
2. Memaketkannya ke dalam bentuk JSON Array.
3. Melakukan autentikasi JWT ke REST API menggunakan kredensial ber-role `collector`.
4. Mengirim (`POST`) muatan tersebut ke endpoint.

## 🚀 Mode Operasi
Terdapat *environment variable* `COLLECTOR_MODE` di dalam `.env` yang bisa diatur:

1. **`demo` (Default)**
   Men-generate nilai *dummy/acak* yang fluktuatif namun tampak realistis. Sangat berguna untuk pengujian UI Dashboard, mempresentasikan laporan, atau *demo* aplikasi. Modul SNMP maupun *HTTP request* asli ke Ceph *manager* dinonaktifkan.

2. **`real` / `hybrid` (Siap Diimplementasi)**
   Struktur kelas (`snmp_collector.py` dan `ceph_collector.py`) sudah dipersiapkan sebagai blok penyusun (*stubs*). Anda cukup mengganti logika pembacaannya dengan *library* pembaca metrik yang riil (contohnya `pysnmp` atau pemanggilan HTTP API asli Ceph).

## 💻 Panduan Menjalankan (Lokal tanpa Docker)
Bila ingin menjalankan / mengembangkan (debug) skrip ini tanpa kontainer *Docker Compose*:

1. **Siapkan Environment**
   ```bash
   cp .env.example .env
   # Edit .env, pastikan URL API sudah benar.
   ```

2. **Buat Virtual Environment (Sangat Disarankan)**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependensi**
   ```bash
   pip install -r requirements.txt
   ```

4. **Jalankan Daemon**
   ```bash
   python metric_collector.py
   ```
