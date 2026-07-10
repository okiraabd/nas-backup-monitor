# Metric Collector

Collector adalah daemon Python yang mengambil metrik NAS dan Ceph secara
berkala, lalu mengirimkannya ke Backup Monitor API.

Endpoint API yang dipakai:

- `POST /api/auth/login`
- `POST /api/monitor/ingest`
- `POST /api/monitor/collector/run`
- `GET /api/monitor/collector/status`

## Cara kerja

Pada setiap siklus:

1. Login ke API memakai akun role `collector`.
2. Ambil metrik NAS dari Prometheus SNMP Exporter.
3. Ambil metrik Ceph dari endpoint Prometheus Ceph manager.
4. Normalisasi metric NAS ke nama yang dipakai dashboard.
5. Kirim batch metric ke API.
6. Kirim status run collector.
7. Tunggu `COLLECTOR_INTERVAL_SECONDS`, lalu ulangi.

Collector membaca endpoint HTTP SNMP Exporter; collector tidak melakukan query
SNMP langsung ke perangkat NAS.

## SNMP Exporter production

Production NAS cukup expose SNMP UDP/161. SNMP Exporter dapat berjalan di server
Linux terpisah dan melakukan query ke NAS dengan endpoint:

```text
/snmp?target=<ip_nas>&module=<module_name>
```

Contoh:

```text
/snmp?target=192.168.24.5&module=synology_nas
/snmp?target=192.168.24.4&module=wd_pr4100
```

Collector mendukung dua mode:

| Mode | Konfigurasi | Keterangan |
|---|---|---|
| Centralized exporter | `SNMP_EXPORTER_URL=http://host:9116/snmp` | Direkomendasikan untuk production. |
| Legacy per-NAS exporter | `SNMP_EXPORTER_URL=` | Collector membaca `http://<ip_nas>:9116/metrics`. |

Template konfigurasi SNMP Exporter ada di
[../snmp-exporter/README.md](../snmp-exporter/README.md).

## Metric NAS yang dinormalisasi

Collector menyimpan nama metric inti berikut agar dashboard tetap stabil:

| Metric | Sumber utama |
|---|---|
| `cpu_usage` | `ssCpuIdle` atau `ssCpuUser + ssCpuSystem` dari UCD-SNMP. |
| `ram_used_pct` | `memTotalReal`, `memAvailReal`, `memBuffer`, `memCached`. |
| `disk_used_pct` | `hrStorage*`, fallback Synology RAID atau WD volume. |
| `temperature` | Synology `temperature`, WD `mycloudpr4100Temperature`, fallback disk temperature. |
| `system_uptime` | `sysUpTime`. |
| `snmp_reachable` | `1` jika scrape berhasil, `0` jika gagal. |

## Konfigurasi

Contoh `.env` lokal:

```env
API_URL=http://localhost:8000/api
COLLECTOR_USERNAME=collector
COLLECTOR_PASSWORD=collector123
COLLECTOR_INTERVAL_SECONDS=60
USE_MOCK_METRICS=false

SNMP_EXPORTER_URL=http://snmp-exporter:9116/snmp?auth=kkp_snmp_v2
SNMP_DEFAULT_MODULE=if_mib
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100

CEPH_METRICS_URL=http://192.168.24.6:9283/metrics
```

`NAS_TARGETS` memakai format:

```text
source_id|ip_address|snmp_exporter_module
```

Format lama masih diterima:

```text
source_id:ip_address
```

Namun format lama tidak bisa menentukan module per NAS, sehingga kurang cocok
untuk production campuran Synology dan WD.

Jika SNMP Exporter memakai auth profile, masukkan auth di base URL:

```env
SNMP_EXPORTER_URL=http://snmp-exporter:9116/snmp?auth=kkp_snmp_v2
```

Collector akan otomatis menambahkan `target` dan `module`.

## Menjalankan lokal

```bash
cd collector
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python metric_collector.py
```

Folder virtual environment (`venv/` atau `.venv/`) tidak perlu dicommit.

## Menjalankan via Docker Compose

```bash
docker compose up -d --build collector
docker compose logs -f collector
```

Jika memakai SNMP Exporter bawaan project, siapkan config lalu aktifkan profile
`snmp`:

```bash
cp snmp-exporter/snmp.yml.example snmp-exporter/snmp.yml
# default SNMP v2 community adalah "public"; edit jika NAS memakai community lain
docker compose --profile snmp up -d snmp-exporter collector
```

## Test manual SNMP Exporter

Sebelum collector diaktifkan, cek output exporter:

```bash
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.24.5&module=synology_nas'
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.24.4&module=wd_pr4100'
```

Minimal output Synology yang ideal:

```text
ssCpuIdle
memTotalReal
hrStorageSize
hrStorageUsed
temperature
sysUpTime
```

Minimal output WD yang ideal:

```text
sysUpTime
mycloudpr4100Temperature
mycloudpr4100VolumeSize
mycloudpr4100VolumeFreeSpace
```

## Troubleshooting

- `401 Unauthorized`: cek `COLLECTOR_USERNAME` dan `COLLECTOR_PASSWORD`.
- `snmp_reachable=0`: cek koneksi collector ke SNMP Exporter dan koneksi exporter ke NAS UDP/161.
- Metric NAS 0: cek apakah module SNMP Exporter menghasilkan nama metric yang dibutuhkan.
- WD disk/temperature 0: cek apakah field DisplayString sudah diekstrak menjadi angka di `snmp.yml`.
- `Temporary failure in name resolution`: biasanya DNS/network Docker sementara setelah API restart; collector akan retry.
- Tidak ada metric Ceph: cek `CEPH_METRICS_URL`.
