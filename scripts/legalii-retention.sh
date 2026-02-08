#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/enterprise/logs"
BACKUP_DIR="${LEGALII_BACKUP_DIR:-$ROOT/enterprise/backups}"
KEEP_LOG_DAYS="${LEGALII_KEEP_LOG_DAYS:-30}"
KEEP_BACKUP_DAYS="${LEGALII_KEEP_BACKUP_DAYS:-14}"

mkdir -p "$LOG_DIR" "$BACKUP_DIR"

find "$LOG_DIR" -type f \( -name "*.log" -o -name "*.jsonl" \) -mtime +"$KEEP_LOG_DAYS" -print -delete || true
find "$BACKUP_DIR" -type f -name "legalii-backup-*.tar.gz" -mtime +"$KEEP_BACKUP_DAYS" -print -delete || true

echo "[OK] retention applied (logs>${KEEP_LOG_DAYS}d, backups>${KEEP_BACKUP_DAYS}d)"
