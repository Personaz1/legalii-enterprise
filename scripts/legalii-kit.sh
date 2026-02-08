#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${LEGALII_HOST:-127.0.0.1}"
PORT="${LEGALII_PORT:-8777}"

fail() { echo "[ERROR] $*" >&2; exit 1; }
info() { echo "[INFO]  $*"; }

preflight() {
  info "Running local preflight checks..."

  command -v python3 >/dev/null 2>&1 || fail "python3 is required"

  # shellcheck disable=SC2016
  python3 - <<'PY' >/dev/null 2>&1 || {
import importlib
mods = ["fastapi", "uvicorn", "multipart"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit(1)
PY
    info "Installing Python deps (fastapi uvicorn python-multipart pypdf python-docx pillow pytesseract reportlab)..."
    python3 -m pip install --user fastapi uvicorn python-multipart pypdf python-docx pillow pytesseract reportlab >/dev/null
  }

  mkdir -p enterprise/logs enterprise/data enterprise/data/ingest
  touch enterprise/logs/audit.log enterprise/logs/review.log enterprise/data/review_queue.jsonl

  info "Preflight passed"
}

preflight

info "Starting LEGALII kit on http://$HOST:$PORT"
python3 -m uvicorn legalii-kit.app:app --host "$HOST" --port "$PORT"
