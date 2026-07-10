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
2. Ambil metrik NAS dari Prometheus SNMP exporter.
3. Ambil metrik Ceph dari endpoint Prometheus Ceph manager.
4. Kirim batch metric ke API.
5. Kirim status run collector.
6. Tunggu `COLLECTOR_INTERVAL_SECONDS`, lalu ulangi.

## Mode operasi

| Mode | Konfigurasi | Keterangan |
|---|---|---|
| Demo/mock | `USE_MOCK_METRICS=true` | Mengirim data simulasi tanpa NAS/Ceph nyata. |
| Real | `USE_MOCK_METRICS=false` | Membaca SNMP exporter NAS dan Ceph metrics endpoint. |

Collector membaca endpoint HTTP exporter; collector tidak melakukan query SNMP
langsung ke perangkat NAS.

## Konfigurasi

Contoh `.env` lokal:

```env
API_URL=http://localhost:8000/api
COLLECTOR_USERNAME=collector
COLLECTOR_PASSWORD=collector123
COLLECTOR_INTERVAL_SECONDS=60
USE_MOCK_METRICS=false
NAS_TARGETS=synology-ds1522:192.168.24.5,wd-pr4100:192.168.24.4
CEPH_METRICS_URL=http://192.168.24.6:9283/metrics
```

Pada Docker Compose, konfigurasi collector diambil dari root `.env`.

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

## Troubleshooting

- `401 Unauthorized`: cek `COLLECTOR_USERNAME` dan `COLLECTOR_PASSWORD`.
- `Temporary failure in name resolution`: biasanya DNS/network Docker sementara setelah API restart; collector akan retry.
- Tidak ada metric NAS: cek `NAS_TARGETS` dan exporter port `9116`.
- Tidak ada metric Ceph: cek `CEPH_METRICS_URL`.
