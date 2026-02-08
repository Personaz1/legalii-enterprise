#!/usr/bin/env bash
set -euo pipefail

BASE="${LEGALII_BASE_URL:-http://127.0.0.1:8777}"
KEY="${LEGALII_API_KEY:-}"
HDR=()
if [ -n "$KEY" ]; then HDR=(-H "x-api-key: $KEY"); fi

req_json() {
  local method="$1"; shift
  local url="$1"; shift
  curl -fsS -X "$method" "$url" "${HDR[@]}" "$@"
}

echo "[1/6] health"
req_json GET "$BASE/health" >/dev/null

CASE_ID="SMOKE-$(date +%s)"
echo "[2/6] create case $CASE_ID"
req_json POST "$BASE/api/v1/cases" -H 'content-type: application/json' --data "{\"case_id\":\"$CASE_ID\",\"case_type\":\"asilo\",\"title\":\"Smoke\",\"client_name\":\"Smoke Client\"}" >/dev/null

echo "[3/6] analyze sample into case"
TMP_JSON="$(mktemp /tmp/legalii-smoke.XXXXXX.json)"
cat > "$TMP_JSON" <<'JSON'
{"case_id":"SMK-1","case_type":"asilo","applicant":{"full_name":"Test User","birth_date":"1990-01-01","passport_number":"X12345"},"documents":[{"doc_type":"pasaporte_o_id","fields":{}},{"doc_type":"solicitud_asilo","fields":{}},{"doc_type":"empadronamiento_o_domicilio","fields":{}}]}
JSON
curl -fsS -X POST "$BASE/api/v1/cases/$CASE_ID/analyze-upload" "${HDR[@]}" -F "file=@$TMP_JSON;type=application/json" >/dev/null

echo "[4/6] list reports"
req_json GET "$BASE/api/v1/cases/$CASE_ID/reports" >/dev/null

echo "[5/6] dossier markdown"
req_json GET "$BASE/api/v1/cases/$CASE_ID/dossier-markdown" >/dev/null

echo "[6/6] backup"
"$(cd "$(dirname "$0")" && pwd)/legalii-backup.sh" >/dev/null

rm -f "$TMP_JSON"
echo "[OK] smoke passed"
