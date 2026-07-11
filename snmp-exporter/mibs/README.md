# MIB Vendor untuk SNMP Exporter

Direktori ini adalah lokasi kerja sementara untuk MIB vendor ketika menghasilkan
snmp.yml dari generator.yml. MIB tidak disertakan di repositori karena dapat
memiliki lisensi vendor, berbeda antar-firmware, dan bukan kebutuhan runtime
setelah konfigurasi exporter selesai dibuat.

Kembali ke [README SNMP Exporter](../README.md) untuk alur lengkap.

## Struktur yang direkomendasikan

~~~text
snmp-exporter/mibs/
├── synology/
│   ├── SYNOLOGY-SYSTEM-MIB.txt
│   ├── SYNOLOGY-DISK-MIB.txt
│   ├── SYNOLOGY-RAID-MIB.txt
│   └── ... MIB dependensi yang dibutuhkan generator
└── wd/
    └── MYCLOUDPR4100-MIB.txt
~~~

Gunakan nama file asli yang diberikan vendor bila generator atau dependensi MIB
mengharapkannya. Jangan mengganti MIB produksi dengan file dari model atau
firmware lain tanpa pengujian pada perangkat target.

## Mendapatkan dan memvalidasi MIB

1. Unduh MIB dari portal dokumentasi/support resmi vendor atau sumber yang
   disetujui organisasi.
2. Catat model perangkat, versi firmware, URL/sumber, dan tanggal pengambilan
   pada catatan deployment internal.
3. Salin hanya MIB yang diperlukan ke subdirektori sesuai vendor.
4. Jalankan generator dari versi SNMP Exporter yang sama dengan runtime.
5. Uji hasilnya terhadap perangkat nyata melalui endpoint /snmp.

MIB biasanya memiliki dependensi pada MIB standard atau MIB vendor lain.
Apabila generator tidak dapat me-resolve simbol, tambahkan dependensi yang
sesuai atau gunakan OID numerik yang sudah disediakan generator.yml. Hindari
memodifikasi MIB asli bila bisa diselesaikan lewat konfigurasi generator.

## Kebijakan secret dan version control

- MIB umumnya bukan secret, tetapi tetap review lisensi sebelum meng-commitnya.
- Jangan menyimpan community SNMP, user/auth/priv password SNMPv3, atau dump
  perangkat di direktori ini.
- File snmp.yml production diabaikan Git karena berpotensi memuat auth.
- snmp.yml.example adalah contoh yang sudah disanitasi; community public di
  dalamnya hanya nilai contoh, bukan rekomendasi production.

Setelah snmp.yml tervalidasi dan dipasang, MIB dapat tetap disimpan pada host
generator/deployment sebagai bukti reproduksibilitas. Runtime exporter hanya
memerlukan snmp.yml hasil generator.
