#!/usr/bin/env bash
# Reporter-only agent: Kopia owns backup/scheduling; this script reads results.

set -Eeuo pipefail
umask 077

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
APP_HOME=$SCRIPT_DIR

# Config dapat diberikan eksplisit. Jika tidak, production default-nya adalah
# .env di folder aplikasi yang sama dengan script.
if [[ $# -gt 0 ]]; then
    CONFIG_FILE=$1
else
    CONFIG_FILE="$APP_HOME/.env"
fi

log() {
    printf '%s [kopia-reporter] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

if [[ ! -r "$CONFIG_FILE" ]]; then
    log "Configuration is not readable: $CONFIG_FILE"
    log "Copy .env.example to $APP_HOME/.env and protect it with chmod 600."
    exit 2
fi

# The config is an administrator-owned shell environment file. It must not be
# writable by untrusted users because it is sourced by this process.
set -a
# shellcheck source=/dev/null
source "$CONFIG_FILE"
set +a

# Konfigurasi dibuat minimal: Kopia menyediakan detail job/snapshot,
# sedangkan env hanya memberi identitas NAS dan akses API.
required=(NAS_ID KOPIA_CONTAINER_NAME API_URL SERVICE_USERNAME SERVICE_PASSWORD_FILE)
for name in "${required[@]}"; do
    if [[ -z "${!name:-}" ]]; then
        log "Required configuration is missing: $name"
        exit 2
    fi
done

for command_name in docker curl; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        log "Required command is not installed: $command_name"
        exit 2
    fi
done

# Runtime sengaja berada di bawah APP_HOME agar install NAS cukup satu folder.
RUNTIME_DIR="$APP_HOME/runtime"
PENDING_DIR="$RUNTIME_DIR/pending"
STATE_DIR="$RUNTIME_DIR/state"
DEAD_LETTER_DIR="$RUNTIME_DIR/dead-letter"
TMP_DIR="$RUNTIME_DIR/tmp"
KOPIA_MAX_RESULTS=500
PYTHON_IMAGE="python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df"
CURL_CONNECT_TIMEOUT=5
CURL_MAX_TIME=30
API_URL=${API_URL%/}

mkdir -p "$PENDING_DIR" "$STATE_DIR" "$DEAD_LETTER_DIR" "$TMP_DIR"
chmod 700 "$RUNTIME_DIR" "$PENDING_DIR" "$STATE_DIR" "$DEAD_LETTER_DIR" "$TMP_DIR"

if ! docker image inspect "$PYTHON_IMAGE" >/dev/null 2>&1; then
    log "Reporter Python image is not installed: $PYTHON_IMAGE"
    log "Pre-pull it during installation with: docker pull $PYTHON_IMAGE"
    exit 2
fi

run_reporter_python() {
    # Python selalu disposable container: NAS tidak perlu Python system,
    # dan helper tidak punya akses network.
    local uid gid
    uid=$(id -u)
    gid=$(id -g)

    docker run --rm -i \
        --pull=never \
        --network=none \
        --read-only \
        --cap-drop=ALL \
        --security-opt=no-new-privileges:true \
        --pids-limit=64 \
        --user "$uid:$gid" \
        --env PYTHONDONTWRITEBYTECODE=1 \
        --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
        --volume "$SCRIPT_DIR:/app:ro" \
        --volume "$RUNTIME_DIR:/runtime:rw" \
        "$PYTHON_IMAGE" \
        python3 "$@"
}

# File state/pending dipisah per NAS agar satu host bisa dipakai ulang di lab.
safe_nas=$(printf '%s' "$NAS_ID" | tr -c 'A-Za-z0-9_.-' '_')
STATE_FILE="$STATE_DIR/${safe_nas}.json"
RAW_FILE=$(mktemp "$TMP_DIR/kopia-snapshots.XXXXXX.json")
ERROR_FILE=$(mktemp "$TMP_DIR/kopia-snapshots.XXXXXX.err")
LOGIN_BODY=$(mktemp "$TMP_DIR/api-login.XXXXXX.json")
LOGIN_REQUEST=$(mktemp "$TMP_DIR/api-login-request.XXXXXX.json")
RESPONSE_BODY=$(mktemp "$TMP_DIR/api-response.XXXXXX.json")
LOCK_DIR=""

cleanup() {
    rm -f -- "$RAW_FILE" "$ERROR_FILE" "$LOGIN_BODY" "$LOGIN_REQUEST" "$RESPONSE_BODY"
    unset TOKEN SERVICE_PASSWORD
    if [[ -n "$LOCK_DIR" ]]; then
        rmdir -- "$LOCK_DIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

# Hindari dua reporter berjalan bersamaan dan menulis state/pending yang sama.
if command -v flock >/dev/null 2>&1; then
    exec 9>"$RUNTIME_DIR/${safe_nas}.lock"
    if ! flock -n 9; then
        log "Another reporter process is already running for $NAS_ID."
        exit 0
    fi
else
    LOCK_DIR="$RUNTIME_DIR/${safe_nas}.lockdir"
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        log "Another reporter process is already running, or a stale lock exists: $LOCK_DIR"
        exit 0
    fi
fi

if [[ $(docker inspect --format '{{.State.Running}}' "$KOPIA_CONTAINER_NAME" 2>/dev/null || true) != "true" ]]; then
    log "Kopia container is not running: $KOPIA_CONTAINER_NAME"
    exit 1
fi

# Reporter hanya membaca hasil backup. Schedule dan snapshot create tetap milik Kopia.
kopia_args=(
    snapshot list
    --json
    --json-verbose
    --manifest-id
    --show-identical
    --incomplete
    --no-human-readable
    --max-results="$KOPIA_MAX_RESULTS"
)

log "Scanning up to $KOPIA_MAX_RESULTS snapshots across all Kopia sources"
if ! docker exec "$KOPIA_CONTAINER_NAME" kopia "${kopia_args[@]}" >"$RAW_FILE" 2>"$ERROR_FILE"; then
    log "Kopia snapshot query failed. Last diagnostic lines:"
    tail -n 10 "$ERROR_FILE" >&2 || true
    exit 1
fi

# Helper mengubah JSON Kopia menjadi payload API dan menaruh snapshot baru ke pending.
reconcile_args=(
    /app/kopia_reporter.py reconcile
    --input /dev/stdin
    --state "/runtime/state/$(basename -- "$STATE_FILE")"
    --pending-dir /runtime/pending
    --nas-id "$NAS_ID"
)

if ! parser_result=$(run_reporter_python "${reconcile_args[@]}" <"$RAW_FILE"); then
    log "Snapshot parsing failed inside the disposable Python container."
    exit 1
fi
log "Reconciliation result: $parser_result"

shopt -s nullglob
files=("$PENDING_DIR"/*.json)
if (( ${#files[@]} == 0 )); then
    log "No pending backup logs."
    exit 0
fi

# Password service account dipisah dari .env agar file config tidak berisi secret.
if [[ ! -r "$SERVICE_PASSWORD_FILE" ]]; then
    log "Service password file is not readable: $SERVICE_PASSWORD_FILE"
    exit 2
fi
SERVICE_PASSWORD=$(head -n 1 "$SERVICE_PASSWORD_FILE")
if [[ -z "$SERVICE_PASSWORD" ]]; then
    log "Service password file is empty: $SERVICE_PASSWORD_FILE"
    exit 2
fi

if ! printf '%s\0%s' "$SERVICE_USERNAME" "$SERVICE_PASSWORD" \
    | run_reporter_python /app/kopia_reporter.py login-payload >"$LOGIN_REQUEST"; then
    log "Could not create the API login payload."
    exit 1
fi

login_code=$(curl --silent --show-error \
    --connect-timeout "$CURL_CONNECT_TIMEOUT" \
    --max-time "$CURL_MAX_TIME" \
    --output "$LOGIN_BODY" \
    --write-out '%{http_code}' \
    --request POST "$API_URL/auth/login" \
    --header 'Content-Type: application/json' \
    --data-binary "@$LOGIN_REQUEST" || true)

rm -f -- "$LOGIN_REQUEST"
unset SERVICE_PASSWORD

if [[ "$login_code" != "200" ]]; then
    log "API login failed (HTTP ${login_code:-000}); pending files were preserved."
    exit 1
fi

if ! TOKEN=$(run_reporter_python /app/kopia_reporter.py extract-token <"$LOGIN_BODY"); then
    log "API login response did not contain a valid access token."
    exit 1
fi

# Pending payload dikirim satu per satu. Error sementara tidak menghapus file;
# payload invalid dipindah ke dead-letter agar tidak diproses tanpa akhir.
delivered=0
failed=0
dead_lettered=0
for file in "${files[@]}"; do
    : > "$RESPONSE_BODY"
    http_code=$(curl --silent --show-error \
        --connect-timeout "$CURL_CONNECT_TIMEOUT" \
        --max-time "$CURL_MAX_TIME" \
        --retry 2 \
        --retry-all-errors \
        --output "$RESPONSE_BODY" \
        --write-out '%{http_code}' \
        --request POST "$API_URL/logs/ingest" \
        --header "Authorization: Bearer $TOKEN" \
        --header 'Content-Type: application/json' \
        --data-binary "@$file" || true)

    case "$http_code" in
        200|201)
            rm -f -- "$file"
            delivered=$((delivered + 1))
            ;;
        400|409|422)
            target="$DEAD_LETTER_DIR/$(basename -- "$file").rejected-${http_code}"
            mv -- "$file" "$target"
            log "Rejected payload moved to dead-letter (HTTP $http_code): $(basename -- "$target")"
            dead_lettered=$((dead_lettered + 1))
            ;;
        401|403)
            log "Authorization failed (HTTP $http_code); remaining files were preserved."
            failed=$((failed + 1))
            break
            ;;
        *)
            log "Delivery failed (HTTP ${http_code:-000}); preserving $(basename -- "$file")."
            failed=$((failed + 1))
            ;;
    esac
done

log "Delivery summary: delivered=$delivered dead_lettered=$dead_lettered failed=$failed"
(( failed == 0 ))
