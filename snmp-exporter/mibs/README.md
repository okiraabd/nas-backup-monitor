# MIB files

Place vendor MIB files here only when generating `snmp.yml`.

Recommended layout:

```text
snmp-exporter/mibs/
  synology/
    SYNOLOGY-SYSTEM-MIB.txt
    SYNOLOGY-DISK-MIB.txt
    SYNOLOGY-RAID-MIB.txt
    ...
  wd/
    MYCLOUDPR4100-MIB.txt
```

The generated production `snmp.yml` may contain SNMP auth settings, so keep it
outside git or commit only a sanitized example.
