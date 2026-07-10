# Kopia Backup Result Reporter

Folder ini berisi agen NAS yang membaca hasil backup dari Kopia Server dan
mengirimkannya ke Backup Monitor API. **Kopia tetap memiliki backup, schedule,
retention, dan upload ke S3.** Reporter tidak pernah menjalankan
`kopia snapshot create`.

## Alur

```text
Kopia scheduler -> kopia snapshot list --json -> disposable Python helper
                                                    -> pending queue
                                                    -> POST /api/logs/ingest
```

`kopia_snapshot_reporter.sh` membaca semua source Kopia secara default. Nama job dibuat
otomatis dari metadata snapshot:

```text
source.path         rootEntry.name   job_name
/MAKUKU             MAKUKU           backup-makuku
/master_backup/hr   hr               backup-hr
```

State lokal hanya cache. PostgreSQL tetap menjadi pagar final anti-duplikasi
melalui kombinasi unik `nas_id + job_name + snapshot_id`.

## File utama

- `kopia_snapshot_reporter.sh`: satu entrypoint shell untuk scan, reconcile, login API, dan delivery pending log.
- `kopia_reporter.py`: helper Python untuk parsing JSON Kopia, auto-discovery job, state, pending write, dan auth JSON kecil.
- `.env.example`: template konfigurasi satu NAS. File runtime cukup bernama `.env`.
- `tests/`: fixture Kopia dan test reporter.

Python tidak perlu diinstal di NAS. `kopia_reporter.py` selalu dijalankan lewat
container Python sekali pakai yang dipin dengan digest.

Untuk production NAS, semua file reporter sengaja ditaruh dalam satu folder
aplikasi:

```text
/opt/nas-backup-monitor/
  kopia_snapshot_reporter.sh
  kopia_reporter.py
  .env
  secrets/
    service.password
  runtime/
    pending/
    state/
    dead-letter/
    tmp/
  logs/
    nas-backup-monitor.log
```

Model satu folder ini lebih mudah diaudit, dipindahkan, dan dibackup pada NAS.
Pastikan `/opt` di NAS bersifat persistent. Jika `/opt` tidak persistent pada
NAS tertentu, gunakan folder appdata persistent lain lalu jalankan script dari
folder tersebut.

## Prasyarat NAS

- Bash
- Docker CLI dengan akses ke container Kopia
- curl
- `flock` direkomendasikan; fallback lock-directory tersedia

Source yang dibaca harus sudah terdaftar sebagai policy Kopia.

## Instalasi

```bash
sudo install -d -m 700 /opt/nas-backup-monitor
sudo install -d -m 700 /opt/nas-backup-monitor/secrets
sudo install -d -m 700 /opt/nas-backup-monitor/runtime
sudo install -d -m 700 /opt/nas-backup-monitor/logs
sudo install -m 755 kopia_snapshot_reporter.sh /opt/nas-backup-monitor/
sudo install -m 644 kopia_reporter.py /opt/nas-backup-monitor/
sudo cp .env.example /opt/nas-backup-monitor/.env
sudo chmod 600 /opt/nas-backup-monitor/.env
sudo sh -c 'umask 077; printf "%s\n" "CHANGE_ME" > /opt/nas-backup-monitor/secrets/service.password'
docker pull python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df
```

Sesuaikan `NAS_ID`, API URL, dan service account pada file konfigurasi. Jangan
commit password ke repository.

Reporter sengaja tidak memiliki opsi konfigurasi per job. Semua job, path,
status, ukuran, jumlah file, durasi, dan snapshot ID diambil dari output Kopia.
Nilai seperti `source_ip` dan `destination_target` dikirim `null` karena tidak
tersedia secara stabil di `kopia snapshot list --json`.

Script memakai image Python 3.12 Alpine yang sudah dipin dengan digest dan
`--pull=never`. Ini membuat cron gagal dengan pesan yang jelas jika image belum
tersedia, alih-alih mengunduh image tanpa direncanakan. Container Python
dijalankan tanpa network, read-only, tanpa Linux capabilities, menggunakan
UID/GID pemanggil, dan hanya memperoleh akses tulis ke runtime reporter.

## Konfigurasi satu NAS

Mode default adalah auto-discovery semua source:

```env
NAS_ID=mycloudmakuku
KOPIA_CONTAINER_NAME=kopia-server
API_URL=http://192.168.24.6:8000/api
SERVICE_USERNAME=nas-wd
SERVICE_PASSWORD_FILE=/opt/nas-backup-monitor/secrets/service.password
```

Pada first run, reporter mengantrekan snapshot terbaru dari setiap source Kopia
dan menandai snapshot lama sebagai baseline. Setelah itu, setiap snapshot ID
baru akan dikirim sekali. Runtime berada di `/opt/nas-backup-monitor/runtime`,
scan dibatasi 500 snapshot terbaru, dan nama job selalu `backup-<nama-source>`.

## Menjalankan manual

```bash
/opt/nas-backup-monitor/kopia_snapshot_reporter.sh
```

Runtime disimpan di `/opt/nas-backup-monitor/runtime`:

```text
pending/       payload menunggu API
state/         cache snapshot ID yang sudah ditemukan, per source Kopia
dead-letter/   payload invalid/konflik
tmp/           response dan output sementara
```

HTTP `200` (snapshot sudah ada) dan `201` (snapshot baru) sama-sama dianggap
sukses. HTTP `400`, `409`, dan `422` dipindah ke dead-letter. Gangguan network,
`5xx`, `401`, atau `403` tidak menghapus pending payload.

## Cron

Jalankan reporter lebih sering atau sama sering dengan schedule Kopia. Hindari
waktu yang benar-benar sama agar scan tidak selalu terjadi ketika snapshot
sedang berjalan. Contoh Kopia setiap 10 menit, reporter pada menit ke-2:

```cron
2-59/10 * * * * root /opt/nas-backup-monitor/kopia_snapshot_reporter.sh >> /opt/nas-backup-monitor/logs/nas-backup-monitor.log 2>&1
```

## Test reporter

```bash
docker run --rm \
  --pull=never \
  --network=none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  --volume "$PWD:/app:ro" \
  python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df \
  python3 -m unittest discover -s /app/tests -v
```

Fixture test berasal dari output staging Kopia 0.23.1 yang sudah disanitasi dan
test tambahan memakai bentuk snapshot NAS WD `/MAKUKU`.

## Keterbatasan

Polling snapshot dapat membaca snapshot sukses dan incomplete yang mempunyai
manifest. Kegagalan sebelum manifest terbentuk (misalnya container mati atau
repository tidak dapat dibuka) tidak selalu muncul pada `snapshot list`; hal
tersebut dapat dikembangkan melalui webhook atau missing-schedule monitoring.
