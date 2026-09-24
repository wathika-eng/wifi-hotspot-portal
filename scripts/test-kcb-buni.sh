#!/usr/bin/env bash
set -euo pipefail

: "${KCB_BUNI_TOKEN_URL:?Set KCB_BUNI_TOKEN_URL in .env}"
: "${KCB_BUNI_CONSUMER_KEY:?Set KCB_BUNI_CONSUMER_KEY in .env}"
: "${KCB_BUNI_CONSUMER_SECRET:?Set KCB_BUNI_CONSUMER_SECRET in .env}"

tmp_response="$(mktemp)"
trap 'rm -f "$tmp_response"' EXIT

status="$(curl -sS -o "$tmp_response" -w '%{http_code}' \
  -u "${KCB_BUNI_CONSUMER_KEY}:${KCB_BUNI_CONSUMER_SECRET}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'grant_type=client_credentials' \
  "$KCB_BUNI_TOKEN_URL")"

if [[ "$status" != 2* ]]; then
  echo "KCB token request failed (HTTP ${status})" >&2
  python3 - "$tmp_response" <<'PY'
import json, sys
try:
    payload = json.load(open(sys.argv[1]))
    print(payload.get("error_description") or payload.get("error") or "response body suppressed")
except Exception:
    print("response body suppressed")
PY
  exit 1
fi

python3 - "$tmp_response" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
print(f"KCB OAuth reachable; token_type={payload.get('token_type', 'unknown')} expires_in={payload.get('expires_in', 'unknown')}s")
print("Bearer token acquired successfully (value intentionally not printed).")
PY

echo "STK Push was not sent. Use the application flow after configuring a plan, callback, and idempotency key."
