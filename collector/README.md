# Metric Collector

Metric Collector adalah daemon Python yang mengambil metrik NAS dan Ceph secara
berkala, menormalisasinya ke kontrak dashboard, lalu mengirimkannya ke Backup
Monitor API. Collector tidak berbicara SNMP secara langsung.

~~~text
NAS ── SNMP UDP/161 ──► SNMP Exporter ── HTTP Prometheus ──► Collector ──► API
Ceph mgr ─────────────────── HTTP /metrics ───────────────────► Collector ──► API
~~~

Lihat [README root](../README.md) untuk arsitektur dan Compose, serta
[README SNMP Exporter](../snmp-exporter/README.md) untuk konfigurasi perangkat
dan module.

## Perilaku setiap siklus

Pada setiap run, collector:

1. Login ke API menggunakan akun berperan collector bila belum memegang token.
2. Mengumpulkan satu batch metric dari setiap NAS dalam NAS_TARGETS.
3. Mengumpulkan satu batch metric dari Ceph dengan source_id ceph-cluster.
4. Mengirim setiap batch ke POST /api/monitor/ingest.
5. Mencatat hasil siklus ke POST /api/monitor/collector/run.
6. Menunggu COLLECTOR_INTERVAL_SECONDS sebelum run berikutnya.

Di masa tunggu, collector memeriksa status collector tiap dua detik. Jika
dashboard membuat marker PENDING melalui endpoint run-once, collector keluar
dari masa tunggu dan menjalankan siklus baru. Tombol dashboard tidak dapat
menjalankan container collector secara langsung.

Token 401 ketika ingest membuat collector login lagi pada siklus selanjutnya.
Collector tidak mempunyai persistent retry queue; kegagalan request akan dicoba
lagi pada interval berikutnya.

## Mode operasi

| Mode | USE_MOCK_METRICS | Perilaku |
|---|---|---|
| Demo/mock | true | Menghasilkan metric acak NAS dan Ceph; tidak menghubungi target nyata. |
| Real | false | Scrape SNMP Exporter untuk NAS dan endpoint Prometheus Ceph. |

Gunakan mock hanya untuk demo, UI development, atau test. Status collector
menyimpan penanda is_mock agar dashboard dapat membedakan data simulasi.

## Konfigurasi

Salin collector/.env.example menjadi collector/.env untuk menjalankan daemon
lokal. Dalam Docker Compose, variabel yang sama diwariskan dari file .env di
root proyek.

| Variabel | Default kode | Keterangan |
|---|---:|---|
| API_URL | http://localhost:8000/api | Base URL API tanpa slash akhir. Dalam Compose gunakan http://api:8000/api. |
| COLLECTOR_USERNAME | collector | Akun API dengan role collector. |
| COLLECTOR_PASSWORD | collector123 | Password akun collector. Ganti di production. |
| COLLECTOR_INTERVAL_SECONDS | 60 | Jeda polling dalam detik. |
| USE_MOCK_METRICS | false | true untuk mode demo. |
| SNMP_EXPORTER_URL | kosong | Base endpoint centralized /snmp; kosong mengaktifkan mode legacy. |
| SNMP_DEFAULT_MODULE | if_mib | Module fallback target. |
| NAS_TARGETS | dua contoh target | Daftar NAS dipisahkan koma. |
| CEPH_METRICS_URL | endpoint contoh Ceph | Endpoint Prometheus Ceph manager. |

Kredensial collector harus cocok dengan user aktif di API. Saat memakai seed
demo, nilainya adalah collector dan collector123. Jika .env menggunakan
placeholder seperti my_collector_user, buat/rotasi user yang sesuai terlebih
dahulu atau collector akan mendapat 401.

### Format NAS_TARGETS

Format yang direkomendasikan:

~~~text
source_id|ip_address|module_name|profile
~~~

profile bersifat opsional. Nilainya dapat synology atau wd dan hanya diperlukan
bila nama module tidak cukup untuk melakukan inferensi profile. Contoh:

~~~env
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas|synology,wd-pr4100|192.168.24.4|wd_pr4100|wd
~~~

Format tiga bagian adalah bentuk umum:

~~~env
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100
~~~

Format legacy source_id:ip_address tetap diterima, tetapi hanya memakai
SNMP_DEFAULT_MODULE dan tidak cocok untuk campuran perangkat:

~~~env
NAS_TARGETS=nas-lama:192.168.24.5
~~~

Target invalid diabaikan dengan warning pada log. source_id menjadi identitas
persisten metric dan sebaiknya tidak diganti tanpa alasan.

## Mengambil metrik NAS

### Mode centralized exporter

Ini mode yang direkomendasikan. SNMP Exporter berada di host terpusat dan
collector membentuk request berikut:

~~~text
SNMP_EXPORTER_URL[?query_yang_sudah_ada]&target=IP_NAS&module=MODULE
~~~

Contoh:

~~~env
SNMP_EXPORTER_URL=http://snmp-exporter:9116/snmp?auth=kkp_snmp_v2
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100
~~~

Collector mempertahankan query yang sudah ada, misalnya auth=kkp_snmp_v2, lalu
menambahkan target dan module. Field profile pada NAS_TARGETS bukan auth SNMP;
ia hanya petunjuk normalisasi lokal ketika nama module tidak cukup jelas.
Hindari meletakkan exporter di internet publik.

### Mode legacy per target

Jika SNMP_EXPORTER_URL kosong, collector meminta:

~~~text
http://IP_NAS:9116/metrics
~~~

Mode ini mengasumsikan setiap target mengekspos SNMP Exporter sendiri pada port
9116. Itu berbeda dengan perangkat NAS yang hanya mengekspos SNMP UDP/161.
Gunakan centralized exporter untuk deployment baru.

### Normalisasi NAS

Dashboard selalu menerima delapan metric NAS berikut, terlepas dari nama MIB
vendor:

| Metric API | Unit | Sumber/perhitungan |
|---|---|---|
| cpu_usage | % | 100 - ssCpuIdle; fallback ssCpuUser + ssCpuSystem. |
| ram_used_pct | % | memTotalReal dibanding memAvailReal + buffer + cache. |
| disk_used_pct | % | hrStorage terlebih dahulu; fallback RAID Synology atau volume WD. |
| storage_total_bytes | bytes | Total storage dari hrStorage, RAID Synology, atau volume WD. |
| storage_used_bytes | bytes | Storage terpakai dari sumber yang sama dengan disk_used_pct. |
| temperature | C | Temperatur sistem; fallback temperatur disk maksimum. |
| system_uptime | seconds | sysUpTime TimeTicks dibagi 100. |
| snmp_reachable | bool | 1 jika scrape exporter berhasil, 0 jika gagal. |

Parser dapat membaca output Prometheus normal maupun nilai WD DisplayString
yang menjadi label. Persentase dibatasi ke rentang 0–100.

Jika request ke exporter atau perangkat gagal, collector tetap membangun batch
NAS dengan nilai 0 dan snmp_reachable=0. Bila ingest ke API berhasil, sumber
tersebut tetap dihitung sukses pada collector run; gunakan metric reachability
dan snapshot NAS untuk membedakan kegagalan perangkat dari kegagalan collector.

## Mengambil metrik Ceph

Dalam mode real, collector membaca CEPH_METRICS_URL sebagai text exposition
Prometheus. Metric berikut dikirim:

| Metric API | Asal / arti |
|---|---|
| health_status | ceph_health_status diterjemahkan menjadi HEALTH_OK, HEALTH_WARN, atau HEALTH_ERR. |
| health_detail | Alert aktif dari ceph_health_detail. |
| osd_up / osd_total | Jumlah series ceph_osd_up dan ceph_osd_in yang aktif. |
| storage_total_bytes / storage_used_bytes | ceph_cluster_total_bytes dan ceph_cluster_total_used_bytes. |
| storage_used_pct | Perhitungan used / total. |
| read_iops / write_iops | Saat ini selalu 0 pada mode real. |
| ceph_reachable | 1 untuk scrape berhasil, 0 untuk fallback error. |

Jika Ceph tidak dapat di-scrape, collector mengirim health UNKNOWN dan semua
nilai numeric 0, termasuk ceph_reachable=0. Seperti NAS, batch fallback dapat
berhasil dikirim ke API sehingga status process collector saja bukan bukti
Ceph sehat.

IOPS real belum dihitung karena metric yang dibaca berupa counter dan collector
tidak menyimpan state antar-sampel untuk menghitung rate.

## Menjalankan

### Local

~~~bash
cd collector
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python metric_collector.py
~~~

Pastikan API sudah hidup dan API_URL dapat dijangkau dari host ini. Hentikan
daemon dengan Ctrl+C.

### Docker Compose

Untuk demo:

~~~bash
docker compose up -d --build collector
docker compose logs -f collector
~~~

Untuk monitoring nyata dengan service SNMP Exporter bawaan:

~~~bash
cp snmp-exporter/snmp.yml.example snmp-exporter/snmp.yml
# Perbarui secret auth dan target pada .env.
docker compose --profile snmp up -d --build snmp-exporter collector
~~~

Service snmp-exporter hanya ada pada profile snmp. Compose default tidak
memulainya, bahkan jika SNMP_EXPORTER_URL menunjuk hostname snmp-exporter.

## Verifikasi sebelum mengaktifkan real mode

Uji exporter dari host yang dapat menjangkaunya:

~~~bash
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.24.5&module=synology_nas'
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.24.4&module=wd_pr4100'
curl http://192.168.24.6:9283/metrics
~~~

Output Synology idealnya memuat ssCpuIdle, memTotalReal, hrStorageSize,
hrStorageUsed, temperature, dan sysUpTime. WD idealnya memuat sysUpTime,
mycloudpr4100Temperature, mycloudpr4100VolumeSize, dan
mycloudpr4100VolumeFreeSpace.

Setelah itu ubah USE_MOCK_METRICS=false, rebuild collector bila memakai
Compose, dan periksa:

~~~bash
docker compose logs -f collector
~~~

## Pengujian

Test tidak membutuhkan NAS, Ceph, atau API:

~~~bash
cd collector
python -m unittest discover -s tests -v
~~~

Atau dari root:

~~~bash
docker compose run --rm --no-deps --entrypoint python collector -m unittest discover -s tests -v
~~~

Suite menguji normalisasi Synology, nilai DisplayString WD, pembentukan URL
exporter yang sudah memiliki auth query, serta parsing metric Ceph dengan mock
HTTP response.

## Keamanan dan troubleshooting

- Gunakan akun collector khusus, bukan akun admin.
- Simpan password di secret manager atau .env yang tidak dapat dibaca pengguna
  lain; jangan commit file runtime.
- Batasi akses HTTP SNMP Exporter hanya dari collector.
- Batasi SNMP UDP/161 pada NAS hanya dari host exporter.
- Gunakan TLS/reverse proxy untuk API jika collector berjalan lintas jaringan
  tepercaya.

| Gejala | Penyebab/pemeriksaan |
|---|---|
| Login gagal atau 401 | Periksa API_URL dan pasangan COLLECTOR_USERNAME/PASSWORD. |
| snmp_reachable=0 | Uji URL exporter, route collector → exporter, lalu UDP/161 exporter → NAS. |
| Semua metric NAS 0 tetapi reachable=1 | Module/MIB tidak mengeluarkan nama metric yang dapat dinormalisasi; inspeksi output exporter. |
| Ceph health UNKNOWN | Cek CEPH_METRICS_URL dan akses ke endpoint mgr Prometheus. |
| Collector tidak merespons Run once | Pastikan daemon hidup; ia memeriksa marker PENDING ketika menunggu interval. |
| Metric tetap mock | Periksa USE_MOCK_METRICS, rebuild/recreate container, lalu lihat is_mock pada status collector. |
