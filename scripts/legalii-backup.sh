#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_DATA="$ROOT/enterprise/data"
SRC_LOGS="$ROOT/enterprise/logs"
OUT_DIR="${LEGALII_BACKUP_DIR:-$ROOT/enterprise/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BUNDLE="$OUT_DIR/legalii-backup-$STAMP.tar.gz"

mkdir -p "$OUT_DIR"
[ -d "$SRC_DATA" ] || { echo "[ERROR] missing data dir: $SRC_DATA"; exit 1; }
[ -d "$SRC_LOGS" ] || { echo "[ERROR] missing logs dir: $SRC_LOGS"; exit 1; }

tar -czf "$BUNDLE" -C "$ROOT/enterprise" data logs

echo "[OK] backup created: $BUNDLE"
