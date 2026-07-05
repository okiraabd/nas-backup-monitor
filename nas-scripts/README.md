# NAS Backup Scripts

Folder ini berisi sekumpulan **template script Bash** yang dirancang untuk didistribusikan (ditanam) di masing-masing perangkat keras (NAS) klien, seperti *Synology*, *QNAP*, atau *Western Digital*.

Script ini bertindak sebagai *agen* terdesentralisasi dari arsitektur pusat kita. NAS bertugas untuk mengeksekusi mesin (*engine*) pencadangan Kopia, lalu melaporkan jejak hasilnya (berupa objek JSON) secara pasif ke sentral REST API kita melalui endpoint `POST /api/logs/ingest`.

## 📂 Daftar Script

### 1. `kopia_backup.sh`
Ini adalah *script* pelaksana utama (*Executor*) yang nantinya akan di-trigger oleh penjadwalan `cron` di dalam NAS klien.
Tugasnya meliputi:
- Menginisiasi *Docker container* Kopia CLI untuk melakukan sinkronisasi data lokal ke Ceph.
- Menangkap nilai pengembalian (*exit code*) milik proses Kopia (`0` untuk sukses, selainnya berarti gagal).
- Menyusun sebuah file `payload.json` yang memuat detail metrik cadangan tersebut.
- Menyimpan JSON tersebut secara lokal di dalam folder `pending/`.
- Memanggil `retry_pending_logs.sh` secara instan.

### 2. `retry_pending_logs.sh`
Ini adalah *script* kurir (*Delivery Agent*) yang cerdas dan tangguh (*resilient*).
Tugasnya meliputi:
- Membaca dan memindai semua file JSON tunggakan yang ada di folder `pending/`.
- Meminta akses Token JWT ke API dengan menggunakan akun ber-role *Service* (seperti `nas-synology` / `nas-wd`).
- Melakukan POST untuk menyuntikkan (ingest) data log tersebut.
- **Resilience**: Jika pengiriman berhasil (`HTTP 201`), file di NAS akan dihapus. Sebaliknya, jika API sedang mati (*down*) atau tidak ada koneksi internet, file JSON dibiarkan agar tidak hilang, dan proses akan dicoba ulang otomatis saat penjadwalan (*cron*) berikutnya.

## 💻 Cara Penggunaan (Simulasi Lokal)

Anda tidak perlu memiliki NAS sungguhan atau klaster Ceph aktif untuk membuktikan algoritme ini. Anda bisa mengujinya langsung dari Terminal Anda!

1. Pastikan API dan Database sudah menyala (lihat `README.md` utama).
2. Di dalam terminal, masuk ke folder ini, dan jalankan simulasi pencadangan:
   ```bash
   cd nas-scripts
   ./kopia_backup.sh
   ```
3. Perhatikan *log* terminal. Anda akan melihat sistem mengalkulasi simulasi backup, melempar JSON ke API, mendapatkan *token*, lalu membersihkan jejaknya (hapus JSON dari disk lokal) begitu sukses.
4. Anda dapat segera mengecek data baru tersebut di **Web Dashboard** pada tab *Backup Logs*.
