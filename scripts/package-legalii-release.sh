#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="$ROOT/release"
STAMP="$(date +%Y%m%d-%H%M%S)"
PKG_DIR="$OUT_DIR/legalii-enterprise-$STAMP"
TAR_PATH="$OUT_DIR/legalii-enterprise-$STAMP.tar.gz"

mkdir -p "$PKG_DIR" "$OUT_DIR"

copy() {
  local src="$1"
  if [ -e "$ROOT/$src" ]; then
    rsync -a "$ROOT/$src" "$PKG_DIR/"
  else
    echo "[WARN] missing: $src"
  fi
}

copy "legalii-kit"
copy "enterprise"
copy "scripts/legalii-kit.sh"
copy "scripts/legalii-enterprise-up.sh"
copy "LEGALII_QUICKSTART.md"
copy "RELEASE_CHECKLIST.md"
copy "HANDOFF_STATUS.md"

# avoid accidental secret shipping
rm -f "$PKG_DIR/enterprise/.env.enterprise" || true

cat > "$PKG_DIR/README-RELEASE.txt" <<'TXT'
LEGALII Enterprise release bundle

Start local:
  ./scripts/legalii-kit.sh

Start enterprise docker:
  ./scripts/legalii-enterprise-up.sh

Before production:
  complete RELEASE_CHECKLIST.md
TXT

(cd "$OUT_DIR" && tar -czf "$(basename "$TAR_PATH")" "$(basename "$PKG_DIR")")

echo "[OK] Package: $TAR_PATH"
