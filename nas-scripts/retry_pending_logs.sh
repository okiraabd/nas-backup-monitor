#!/bin/bash
# retry_pending_logs.sh - Pushes pending JSON logs to the API

API_URL="http://localhost:8000/api"
USERNAME="nas-synology"
PASSWORD="synology123"
PENDING_DIR="./pending"

mkdir -p "$PENDING_DIR"

# Check if there are any files
shopt -s nullglob
FILES=("$PENDING_DIR"/*.json)
if [ ${#FILES[@]} -eq 0 ]; then
    echo "No pending logs to push."
    exit 0
fi

# 1. Login to get JWT
echo "Logging in to API..."
LOGIN_RES=$(curl -s -X POST "$API_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}")

TOKEN=$(echo "$LOGIN_RES" | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')

if [ -z "$TOKEN" ] || [ "$TOKEN" == "null" ]; then
    echo "Failed to login. API might be unreachable or credentials invalid."
    echo "Will retry later. Pending files preserved."
    exit 1
fi

echo "Login successful. Processing ${#FILES[@]} pending logs..."

# 2. Iterate and push
for f in "${FILES[@]}"; do
    echo "Pushing $f..."
    RES_CODE=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$API_URL/logs/ingest" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d @"$f")
      
    if [ "$RES_CODE" == "201" ]; then
        echo "Successfully ingested $f, removing file."
        rm "$f"
    else
        echo "Failed to ingest $f (HTTP $RES_CODE), keeping file for retry."
    fi
done

echo "Done processing pending logs."
