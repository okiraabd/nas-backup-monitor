# Kopia Backup Result Reporter

Direktori ini berisi agen reporter yang dipasang pada setiap NAS. Reporter
membaca hasil snapshot dari container Kopia Server dan mengirimnya ke Backup
Monitor API. Ia tidak pernah menjalankan kopia snapshot create, mengubah policy
Kopia, mengatur retention, atau mengirim data ke S3/Ceph.

~~~text
Kopia scheduler
      │ membuat snapshot
      ▼
kopia snapshot list --json
      │
      ▼
kopia_snapshot_reporter.sh
      │ Docker Python helper tanpa network
      ├── state cache
      ├── pending queue
      └── dead-letter
      │
      ▼
POST /api/auth/login → POST /api/logs/ingest
~~~

Dokumentasi API dan role service ada di [README API](../api/README.md).

## Isi direktori

| File | Fungsi |
|---|---|
| kopia_snapshot_reporter.sh | Entrypoint Bash: lock, query Kopia, queue, login, dan delivery HTTP. |
| kopia_reporter.py | Helper Python: normalisasi JSON, discovery source/job, state atomik, queue, dan JSON auth kecil. |
| .env.example | Template konfigurasi minimal per NAS. |
| tests/ | Unit test helper dan fixture Kopia yang sudah disanitasi. |

Python tidak perlu dipasang pada NAS. Script menjalankan helper dalam container
Python 3.12 Alpine sekali pakai yang dipin dengan digest dan harus sudah
di-pull sebelum cron berjalan.

## Perilaku dan model data

### Discovery otomatis job

Reporter membaca semua source yang terlihat dari satu perintah:

~~~text
kopia snapshot list --json --json-verbose --manifest-id --show-identical --incomplete --no-human-readable --max-results=500
~~~

Nama job tidak dikonfigurasi manual. Ia dibuat dari nama root Kopia atau basename
source.path:

| source.path | rootEntry.name | job_name |
|---|---|---|
| /MAKUKU | MAKUKU | backup-makuku |
| /master_backup/hr | hr | backup-hr |
| /volume1/data | data | backup-data |

State per source memakai source.path sebagai identitas stabil. Ini disengaja:
source.host dapat berupa hostname container Kopia dan berubah saat container
dibuat ulang.

### Normalisasi status

Satu snapshot menjadi satu payload API. Snapshot dianggap FAILED bila salah
satu kondisi berikut berlaku:

- stats.errorCount lebih dari 0;
- rootEntry.summ.numFailed lebih dari 0;
- Kopia menandai snapshot incomplete atau menyediakan incompleteReason; atau
- snapshot tidak mempunyai endTime.

Snapshot lain dikirim sebagai SUCCESS. Nilai statistik, retention reason, dan
raw snapshot JSON dipertahankan pada payload. source_ip dan
destination_target dikirim null karena data tersebut tidak tersedia secara
stabil dari perintah snapshot list.

### First run dan deduplikasi

Pada first run untuk setiap source, hanya snapshot terbaru yang terlihat
dimasukkan ke pending queue. Snapshot lama ditandai sebagai baseline dalam
state lokal. Setelah itu, setiap snapshot ID yang belum pernah terlihat akan
diantrikan satu kali.

Nama file pending memuat NAS, job, dan snapshot ID sehingga retry lokal tidak
menimpa payload. State juga ditulis atomik dengan izin 0600. PostgreSQL tetap
menjadi pagar akhir: ingest dengan kombinasi nas_id, job_name, snapshot_id yang
sama mengembalikan 200 dan tidak membuat duplikat.

Kehilangan state lokal tidak otomatis membuat payload pending yang sama tertimpa.
Namun, state dan runtime tetap perlu berada pada storage persistent agar
reconciliation bekerja sebagaimana mestinya.

### Failure sebelum snapshot tersedia

Reporter tetap membuat event FAILED tanpa snapshot_id ketika:

| Kejadian | raw_payload.event_type | Scope event |
|---|---|---|
| Container Kopia tidak berjalan | kopia_container_not_running | Satu event per source lama yang diketahui; generic bila belum ada state. |
| kopia snapshot list gagal, misalnya repository/S3 tidak dapat dibuka | kopia_snapshot_query_failed | Satu event per source lama yang diketahui; generic bila belum ada state. |

Event tanpa snapshot_id memang tidak idempoten pada API, karena setiap
kegagalan scan adalah observasi terpisah. Diagnostic terakhir, maksimal 4000
karakter, disimpan dalam raw_payload.

## Prasyarat NAS

- Bash.
- Docker CLI yang dapat inspect, exec, run, dan pull image.
- Akses Docker socket untuk account yang menjalankan script.
- curl.
- flock direkomendasikan; script menyediakan fallback lock-directory.
- Container Kopia Server yang dapat menjalankan perintah kopia.
- Storage persistent untuk folder aplikasi dan runtime.

Script memakai image berikut dan tidak pernah menariknya saat cron berjalan:

~~~text
python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df
~~~

Siapkan image melalui proses deployment yang terkontrol. Bila image tidak ada,
script berhenti dengan exit code 2 dan tidak mencoba download tanpa persetujuan.

## Instalasi production

Contoh di bawah menempatkan seluruh aplikasi pada satu path persistent:

~~~bash
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
~~~

Jika /opt tidak persistent pada model NAS Anda, gunakan direktori appdata
persistent lain. Jangan memasang runtime pada filesystem sementara.

Struktur akhirnya:

~~~text
/opt/nas-backup-monitor/
├── kopia_snapshot_reporter.sh
├── kopia_reporter.py
├── .env
├── secrets/
│   └── service.password
├── runtime/
│   ├── pending/
│   ├── state/
│   ├── dead-letter/
│   └── tmp/
└── logs/
    └── nas-backup-monitor.log
~~~

## Konfigurasi

Script memakai .env di direktori script sebagai default. File konfigurasi
alternatif boleh diberikan sebagai argumen pertama:

~~~bash
/opt/nas-backup-monitor/kopia_snapshot_reporter.sh /path/ke/reporter.env
~~~

File tersebut di-source oleh Bash, sehingga hanya administrator tepercaya yang
boleh dapat menulisnya.

| Variabel | Wajib | Keterangan |
|---|:---:|---|
| NAS_ID | ✓ | Identitas stabil NAS di API, misalnya synology-ds1522. Jangan memakai hostname container Kopia. |
| KOPIA_CONTAINER_NAME | ✓ | Nama container Kopia yang sedang berjalan. |
| API_URL | ✓ | Base URL API termasuk /api, misalnya https://monitor.example.lan/api. |
| SERVICE_USERNAME | ✓ | User API dengan role service. |
| SERVICE_PASSWORD_FILE | ✓ | File password satu baris dengan izin 0600. |

Contoh:

~~~env
NAS_ID=synology-ds1522
KOPIA_CONTAINER_NAME=kopia-server
API_URL=http://192.168.24.6:8000/api
SERVICE_USERNAME=nas-synology
SERVICE_PASSWORD_FILE=/opt/nas-backup-monitor/secrets/service.password
~~~

Buat user service berbeda untuk setiap NAS bila identitas/audit per mesin
diperlukan. Jangan menaruh password langsung di .env atau command line.

## Antrean delivery

Setelah reconcile, setiap payload dalam runtime/pending dikirim satu per satu.
Perlakuannya:

| Respons API / kondisi | Tindakan |
|---|---|
| 200 atau 201 | Hapus file pending karena API sudah menerima/deduplikasi payload. |
| 400, 409, atau 422 | Pindahkan ke runtime/dead-letter agar tidak diulang terus. |
| 401 atau 403 | Hentikan delivery; semua file tersisa dipertahankan. |
| Gangguan jaringan, timeout, 5xx, atau respons lain | Pertahankan file untuk run berikutnya. |

Curl menggunakan connect timeout 5 detik, total timeout 30 detik, dan dua retry
untuk delivery. Runtime memiliki izin 0700. Periksa dead-letter secara rutin:
payload di sana memerlukan perbaikan konfigurasi atau format sebelum dikirim
ulang secara manual.

## Menjalankan dan menjadwalkan

Uji manual terlebih dahulu:

~~~bash
/opt/nas-backup-monitor/kopia_snapshot_reporter.sh
~~~

Jalankan reporter sedikit setelah jadwal Kopia, bukan pada menit yang sama.
Contoh bila Kopia membuat snapshot tiap 10 menit:

~~~cron
2-59/10 * * * * root /opt/nas-backup-monitor/kopia_snapshot_reporter.sh >> /opt/nas-backup-monitor/logs/nas-backup-monitor.log 2>&1
~~~

Script mengambil lock non-blocking per NAS. Jika run sebelumnya masih aktif,
run baru keluar normal dan tidak memproses file yang sama secara paralel.

Pilih interval yang mempertimbangkan:

- jadwal dan durasi backup Kopia;
- kemungkinan snapshot masih incomplete ketika dibaca;
- jumlah maksimum 500 snapshot yang terlihat setiap scan; dan
- target waktu deteksi kegagalan yang diinginkan.

## Keamanan container helper

Helper Python dijalankan dengan karakteristik berikut:

- --pull=never dan --network=none;
- filesystem root read-only;
- seluruh Linux capability dibuang;
- no-new-privileges dan pids limit 64;
- UID/GID pemanggil; serta
- hanya direktori runtime yang dimount read-write.

Secret password tidak diberikan ke helper. Ia hanya dipakai Bash untuk login
dengan curl, lalu di-unset secepat mungkin. Token API disimpan di memori selama
satu run dan tidak ditulis ke runtime.

Tetap lindungi Docker socket: account dengan akses Docker pada umumnya memiliki
hak istimewa tinggi pada NAS.

## Pengujian

Test helper tidak memerlukan Kopia atau API. Image yang dipin harus tersedia
lebih dahulu:

~~~bash
docker run --rm \
  --pull=never \
  --network=none \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
  --volume "$PWD:/app:ro" \
  python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df \
  python3 -m unittest discover -s /app/tests -v
~~~

Suite menguji normalisasi snapshot, auto-discovery job, first-run baseline,
state loss, queue error repository/container, dan payload auth yang memiliki
karakter spesial.

## Troubleshooting

| Gejala | Pemeriksaan |
|---|---|
| Configuration is not readable | Pastikan .env ada di direktori aplikasi, dapat dibaca account cron, dan permission 0600. |
| Required command is not installed | Pasang Docker CLI atau curl pada NAS. |
| Reporter Python image is not installed | Pull image dengan digest yang tercantum saat deployment. |
| Kopia container is not running | Periksa nama KOPIA_CONTAINER_NAME dan status Docker; reporter seharusnya membuat event FAILED. |
| snapshot query failed | Baca diagnostic di log/runtime pending; periksa repository Kopia, kredensial S3, dan jaringan. |
| API login failed | Periksa API_URL, DNS/TLS, user service, dan file password. |
| Pending tidak berkurang | Periksa HTTP status pada log. 4xx tertentu ada di dead-letter, gangguan sementara tetap berada di pending. |
| Another reporter process is already running | Run sebelumnya masih memegang lock atau fallback lockdir stale perlu diperiksa setelah memastikan tidak ada process aktif. |

Untuk masalah payload yang ditolak, gunakan raw payload pada dead-letter dan
kontrak POST /api/logs/ingest di [README API](../api/README.md).
