# Prometheus SNMP Exporter

Direktori ini menyediakan template konfigurasi Prometheus SNMP Exporter untuk
Synology dan WD My Cloud PR4100. Exporter adalah perantara antara NAS yang
berbicara SNMP dan Metric Collector yang membaca HTTP Prometheus.

~~~text
Synology / WD NAS ── SNMP UDP/161 ──► SNMP Exporter ── GET /snmp ──► Collector
~~~

Collector tidak pernah melakukan query SNMP langsung ke NAS. Cara ini
memusatkan kredensial SNMP, firewall rule, serta parsing MIB pada satu host.

Lihat [README collector](../collector/README.md) untuk pengolahan metrik dan
[README root](../README.md) untuk deployment stack.

## File dan status version control

| File/direktori | Status | Kegunaan |
|---|---|---|
| generator.yml | Di-commit | Sumber module dan auth contoh untuk generator. |
| snmp.yml.example | Di-commit | Konfigurasi generated yang sudah disanitasi dengan community public. |
| snmp.yml | Diabaikan Git | Konfigurasi runtime yang dimount Compose; dapat berisi secret. |
| mibs/ | Di-commit tanpa MIB vendor | Lokasi MIB sementara ketika generator dijalankan. |

Jangan commit community SNMP, credential SNMPv3, atau snmp.yml production.
Panduan MIB ada di [mibs/README.md](mibs/README.md).

## Module yang disediakan

| Module | Perangkat | MIB/metric utama |
|---|---|---|
| synology_nas | Synology NAS | sysUpTime, UCD-SNMP CPU/memory, HOST-RESOURCES storage, dan Synology system/disk/RAID. |
| wd_pr4100 | WD My Cloud PR4100 | sysUpTime, standard MIB bila tersedia, serta MYCLOUDPR4100 temperature/volume/disk/UPS. |

Module Synology melakukan walk pada MIB standard dan enterprise 1.3.6.1.4.1.6574.
Module WD melakukan walk pada enterprise 1.3.6.1.4.1.5127. Nilai DisplayString
WD untuk temperatur dan volume diberi regex_extracts agar dapat menjadi gauge
numeric. Collector juga memiliki fallback parser label untuk firmware/config
yang masih mengekspos nilai sebagai label.

Metric yang paling bermanfaat untuk collector:

~~~text
ssCpuIdle                 memTotalReal              memAvailReal
memBuffer                 memCached                 hrStorageSize
hrStorageUsed             hrStorageAllocationUnits  sysUpTime
temperature               raidTotalSize             raidFreeSize
mycloudpr4100Temperature  mycloudpr4100VolumeSize
mycloudpr4100VolumeFreeSpace
~~~

Tidak semua firmware mengekspos semua MIB standard. Collector memakai urutan
fallback untuk disk dan temperatur; lihat tabel normalisasi pada README
collector.

## Opsi deployment

### Service Compose bawaan

Compose menyediakan service snmp-exporter di profile snmp. Profile ini sengaja
tidak aktif secara default agar stack demo tidak bergantung pada konfigurasi
SNMP.

~~~bash
cd ..
cp snmp-exporter/snmp.yml.example snmp-exporter/snmp.yml
# Perbarui auth/community dalam snmp-exporter/snmp.yml jika diperlukan.
docker compose --profile snmp up -d snmp-exporter
docker compose logs -f snmp-exporter
~~~

Service memount snmp.yml sebagai read-only dan, secara default, membind port
ke 127.0.0.1:9116 pada host. Di jaringan Compose, collector mengaksesnya
melalui:

~~~text
http://snmp-exporter:9116/snmp
~~~

Setel konfigurasi collector:

~~~env
SNMP_EXPORTER_URL=http://snmp-exporter:9116/snmp?auth=kkp_snmp_v2
NAS_TARGETS=synology-ds1522|192.168.24.5|synology_nas,wd-pr4100|192.168.24.4|wd_pr4100
~~~

SNMP_EXPORTER_HOST_BIND dan SNMP_EXPORTER_HOST_PORT di root .env hanya
mengontrol akses dari host untuk troubleshooting. Jangan ubah bind menjadi
0.0.0.0 tanpa firewall dan kebutuhan yang jelas.

### Host exporter terpisah

Untuk production dengan beberapa NAS, menjalankan exporter pada satu host Linux
khusus sering lebih mudah dioperasikan. Host tersebut harus dapat:

- menghubungi setiap NAS dengan UDP/161;
- menyediakan HTTP /snmp hanya ke collector; dan
- menyimpan konfigurasi SNMP serta MIB dengan aman.

Contoh URL pada collector:

~~~env
SNMP_EXPORTER_URL=http://snmp-exporter.monitoring.lan:9116/snmp?auth=kkp_snmp_v2
~~~

Jangan menganggap URL HTTP ini aman bila melewati jaringan tidak tepercaya.
Letakkan exporter dan collector pada jaringan privat atau lindungi dengan
reverse proxy/TLS dan ACL yang sesuai.

## Menyiapkan perangkat NAS

Sebelum membuat konfigurasi:

1. Aktifkan SNMP pada NAS sesuai dokumentasi vendor.
2. Batasi ACL perangkat agar hanya IP host SNMP Exporter yang dapat meminta
   UDP/161.
3. Catat versi firmware, alamat IP tetap/reservasi DHCP, dan tipe perangkat.
4. Uji walk/read dari host exporter dengan alat SNMP yang disetujui organisasi.
5. Bila memungkinkan, gunakan SNMPv3. SNMPv2c community adalah secret dan
   berjalan tanpa enkripsi.

Nama module harus cocok dengan target collector:

| NAS | Module pada NAS_TARGETS |
|---|---|
| Synology DS1522+ atau Synology serupa | synology_nas |
| WD My Cloud PR4100 | wd_pr4100 |

## Menghasilkan snmp.yml dari generator.yml

snmp.yml.example sudah cukup untuk mulai menguji profile SNMPv2c public.
Untuk production, buat konfigurasi baru dari generator.yml dan MIB firmware
yang tepat.

Langkah tingkat tinggi:

1. Salin MIB Synology ke mibs/synology dan MYCLOUDPR4100-MIB.txt ke mibs/wd.
2. Salin generator.yml menjadi file kerja aman dan ganti auth contoh dengan
   secret atau profil SNMPv3 yang benar.
3. Jalankan binary generator dari versi Prometheus SNMP Exporter yang akan
   dipakai.
4. Validasi output dan simpan sebagai snmp.yml di luar version control.
5. Uji endpoint /snmp untuk setiap NAS sebelum collector real diaktifkan.

Contoh bentuk perintah generator:

~~~bash
./generator generate \
  -m ./mibs/synology \
  -m ./mibs/wd \
  -g ./generator.yml \
  -o ./snmp.yml
~~~

Ikuti dokumentasi generator yang sesuai dengan versi exporter Anda untuk flag
dan format SNMPv3. Jangan mencampur MIB dari firmware berbeda tanpa validasi.
Jika namespace MIB vendor konflik, hasilkan konfigurasi Synology dan WD secara
terpisah lalu review dan gabungkan bagian auths serta modules dengan hati-hati.

## Verifikasi endpoint

Setelah exporter berjalan, request manual harus menghasilkan text exposition
Prometheus dan bukan HTML/error:

~~~bash
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.24.5&module=synology_nas'
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.24.4&module=wd_pr4100'
~~~

Verifikasi hal berikut sebelum menyalakan collector:

- HTTP response berhasil dan scrape tidak timeout.
- Metric sysUpTime muncul.
- Synology menyediakan CPU/memory serta storage atau fallback RAID.
- WD menyediakan volume size/free dan temperature, bila firmware mendukung.
- Nilai DisplayString WD menjadi angka atau label yang masih dapat diparse.
- Hanya host collector yang dapat mengakses endpoint exporter.

Kemudian set USE_MOCK_METRICS=false pada collector dan amati log collector
serta metric snmp_reachable di dashboard.

## Troubleshooting

| Gejala | Penyebab/pemeriksaan |
|---|---|
| Compose service gagal start | Pastikan snmp-exporter/snmp.yml ada; service memount file runtime, bukan .example. |
| Timeout ketika /snmp dipanggil | Periksa route/ACL UDP 161 dari exporter ke NAS, alamat target, versi SNMP, dan community/credential. |
| auth profile tidak ditemukan | Nama auth pada URL harus cocok dengan bagian auths dalam snmp.yml. |
| Metric vendor tidak muncul | Periksa MIB/firmware, module yang dipilih, dan hasil generator. |
| Disk atau temperatur 0 di dashboard | Bandingkan output /snmp dengan metric fallback yang didukung collector. |
| Exporter dapat diakses dari jaringan luas | Kembalikan bind host ke localhost atau pasang ACL/firewall/reverse proxy. |

## Checklist keamanan

- Jangan mengekspos UDP/161 atau HTTP /snmp ke internet.
- Gunakan ACL NAS: hanya host exporter.
- Gunakan ACL exporter: hanya collector/administrator yang diperlukan.
- Simpan community dan credential SNMPv3 di luar Git.
- Pin SNMP_EXPORTER_IMAGE ke versi atau digest yang direview.
- Putar community/credential bila file runtime atau host exporter diduga bocor.
