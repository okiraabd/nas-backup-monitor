# SNMP exporter configuration

This folder contains the template needed to generate `snmp.yml` for Prometheus
SNMP Exporter. The Backup Monitor collector does not query NAS devices over SNMP
directly; it calls SNMP Exporter over HTTP.

Production flow:

```text
Synology / WD NAS --SNMP UDP/161--> SNMP Exporter --HTTP /snmp--> collector
```

## Files

| File | Purpose |
|---|---|
| `generator.yml` | Template module definition for `synology_nas` and `wd_pr4100`. |
| `mibs/` | Temporary location for vendor MIB files when generating `snmp.yml`. |
| `snmp.yml.example` | Sanitized generated config with placeholder community. Safe to commit. |
| `snmp.yml` | Runtime config mounted by Docker Compose. Do not commit production secrets. |

## Module design

`synology_nas` intentionally combines several MIB families:

- `SNMPv2-MIB` for `sysUpTime`.
- `UCD-SNMP-MIB` for CPU and memory (`ssCpu*`, `mem*`).
- `HOST-RESOURCES-MIB` for filesystem usage (`hrStorage*`).
- `SYNOLOGY-*` MIBs for temperature, disk health, RAID, fan, and status.

`wd_pr4100` combines:

- standard MIBs if the WD firmware exposes them;
- `MYCLOUDPR4100-MIB` for system temperature, volume size/free, fan, disk, and UPS.

## Generate `snmp.yml`

Use the official `prometheus/snmp_exporter` generator on a Linux server that has
the required MIB files available.

High-level steps:

1. Copy Synology MIB files into `snmp-exporter/mibs/synology/`.
2. Copy `MYCLOUDPR4100-MIB.txt` into `snmp-exporter/mibs/wd/`.
3. Replace the placeholder auth in `generator.yml`.
4. Run the SNMP exporter generator and output `snmp.yml`.
5. Run SNMP Exporter with that generated `snmp.yml`.

The official generator accepts custom MIB directories and paths similar to:

```bash
./generator generate \
  -m ./mibs/synology \
  -m ./mibs/wd \
  -g ./generator.yml \
  -o ./snmp.yml
```

If MIB namespace conflicts appear, generate Synology and WD configs separately,
then merge the `auths` and `modules` sections into one `snmp.yml`.

## Run bundled SNMP Exporter

The project includes an optional Docker Compose service named `snmp-exporter`.
It is behind the `snmp` profile so the default stack does not require an SNMP
config file.

Prepare the runtime config:

```bash
cp snmp-exporter/snmp.yml.example snmp-exporter/snmp.yml
```

Then edit `snmp-exporter/snmp.yml` and replace:

```yaml
community: CHANGE_ME_SNMP_COMMUNITY
```

Start the service:

```bash
docker compose --profile snmp up -d snmp-exporter
```

By default, the exporter binds to `127.0.0.1:9116` on the host and is reachable
inside Compose as:

```text
http://snmp-exporter:9116/snmp
```

## Test manually

After SNMP Exporter runs, test each NAS before enabling the collector:

```bash
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.x.x&module=synology_nas'
curl 'http://127.0.0.1:9116/snmp?auth=kkp_snmp_v2&target=192.168.x.y&module=wd_pr4100'
```

Expected important metric names for Backup Monitor:

```text
ssCpuIdle
ssCpuUser
ssCpuSystem
memTotalReal
memAvailReal
memBuffer
memCached
hrStorageSize
hrStorageUsed
hrStorageAllocationUnits
sysUpTime
temperature
raidTotalSize
raidFreeSize
mycloudpr4100Temperature
mycloudpr4100VolumeSize
mycloudpr4100VolumeFreeSpace
```

## Collector environment

Point the collector to the centralized exporter:

```env
SNMP_EXPORTER_URL=http://snmp-exporter:9116/snmp?auth=kkp_snmp_v2
NAS_TARGETS=synology-ds1522|192.168.x.x|synology_nas,wd-pr4100|192.168.x.y|wd_pr4100
```

If SNMP Exporter uses named auth profiles, include the auth query in the base
URL:

```env
SNMP_EXPORTER_URL=http://SNMP_EXPORTER_HOST:9116/snmp?auth=kkp_snmp_v2
```

The collector will append `target` and `module` automatically.

## Security notes

- Do not expose SNMP Exporter to the public internet.
- Restrict access so only the collector can call `/snmp`.
- Prefer SNMPv3 when the NAS supports it.
- Keep real community strings and SNMPv3 credentials outside git.
- Allow SNMP UDP/161 only from the SNMP Exporter server to the NAS.
