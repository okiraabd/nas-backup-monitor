#!/bin/bash
# kopia_backup.sh - Template for running Kopia on a NAS and logging to API

# Configuration
NAS_ID="synology-ds1522"
JOB_NAME="backup-makuku"
SOURCE_PATH="/volume1/MAKUKU"
SOURCE_IP="192.168.1.10"
DESTINATION="Ceph S3"

PENDING_DIR="./pending"
mkdir -p "$PENDING_DIR"

# Timestamp start
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
START_SECONDS=$(date +%s)

echo "Starting backup job: $JOB_NAME"

# 1. Run Kopia via Docker (Mock/Realistic)
# We capture the output and exit code
# In a real scenario: docker run --rm -v $SOURCE_PATH:/data kopia/kopia snapshot create /data --json

# SIMULATION START
# docker run --rm -v "$SOURCE_PATH:/data" kopia/kopia snapshot create /data
sleep 2 # Simulate backup process
EXIT_CODE=0
# SIMULATION END

END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
END_SECONDS=$(date +%s)
DURATION=$((END_SECONDS - START_SECONDS))

STATUS="SUCCESS"
MESSAGE="Kopia snapshot completed successfully"
if [ $EXIT_CODE -ne 0 ]; then
    STATUS="FAILED"
    MESSAGE="Kopia snapshot failed with exit code $EXIT_CODE"
fi

# 2. Extract snapshot info (In real usage, parse Kopia JSON output using jq)
# Here we generate a mock JSON payload representing the backup log
LOG_FILE="$PENDING_DIR/log_${START_SECONDS}.json"

cat <<EOF > "$LOG_FILE"
{
  "nas_id": "$NAS_ID",
  "job_name": "$JOB_NAME",
  "source_path": "$SOURCE_PATH",
  "source_ip": "$SOURCE_IP",
  "destination_target": "$DESTINATION",
  "backup_engine": "kopia",
  "status": "$STATUS",
  "snapshot_id": "snap-$(date +%s)",
  "started_at": "$START_TIME",
  "ended_at": "$END_TIME",
  "duration_seconds": $DURATION,
  "total_size_bytes": 154241124981,
  "total_files": 11579,
  "changed_file_count": 12,
  "cached_files": 11567,
  "non_cached_files": 12,
  "dir_count": 43,
  "error_count": 0,
  "ignored_error_count": 0,
  "retention_reason": ["latest-5"],
  "message": "$MESSAGE",
  "raw_payload": {"simulated": true}
}
EOF

echo "Saved pending log to $LOG_FILE"

# 3. Call the retry script to attempt pushing this and any other pending logs
./retry_pending_logs.sh
