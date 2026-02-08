#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENT_DIR="$ROOT/enterprise"
ENV_FILE="$ENT_DIR/.env.enterprise"
EXAMPLE_ENV="$ENT_DIR/.env.enterprise.example"
COMPOSE_FILE="$ENT_DIR/docker-compose.enterprise.yml"

fail() { echo "[ERROR] $*" >&2; exit 1; }
warn() { echo "[WARN]  $*" >&2; }
info() { echo "[INFO]  $*"; }

preflight() {
  info "Running enterprise preflight checks..."

  command -v docker >/dev/null 2>&1 || fail "docker is required"
  docker info >/dev/null 2>&1 || fail "docker daemon is not running or inaccessible"
  docker compose version >/dev/null 2>&1 || fail "docker compose plugin is required"

  [ -d "$ENT_DIR" ] || fail "enterprise dir not found: $ENT_DIR"
  [ -f "$COMPOSE_FILE" ] || fail "compose file missing: $COMPOSE_FILE"
  [ -f "$EXAMPLE_ENV" ] || fail "missing env example: $EXAMPLE_ENV"

  mkdir -p "$ENT_DIR/logs" "$ENT_DIR/data" "$ENT_DIR/data/ingest"

  if [ ! -f "$ENV_FILE" ]; then
    cp "$EXAMPLE_ENV" "$ENV_FILE"
    warn "Created $ENV_FILE from example"
  fi

  if ! grep -Eq '^LEGALII_REQUIRE_AUTH=true$' "$ENV_FILE"; then
    warn "LEGALII_REQUIRE_AUTH is not explicitly set to true in .env.enterprise"
  fi

  if ! grep -Eq '^LEGALII_API_KEY=.+$' "$ENV_FILE" && ! grep -Eq '^LEGALII_API_KEYS_JSON=.+$' "$ENV_FILE"; then
    warn "No API key configured (LEGALII_API_KEY or LEGALII_API_KEYS_JSON)"
  fi

  if grep -Eq '^LEGALII_API_KEY=change-me' "$ENV_FILE"; then
    warn "LEGALII_API_KEY still uses placeholder value"
  fi
  if grep -Eq '^LEGALII_TOKEN_SECRET=change-me' "$ENV_FILE"; then
    warn "LEGALII_TOKEN_SECRET still uses placeholder value"
  fi
  if grep -Eq '^LEGALII_CORS_ORIGINS=\*$' "$ENV_FILE"; then
    warn "LEGALII_CORS_ORIGINS is wildcard (*) in enterprise env"
  fi

  info "Preflight passed"
}

preflight

cd "$ENT_DIR"
docker compose -f docker-compose.enterprise.yml --env-file .env.enterprise up -d

info "LEGALII Enterprise started"
info "Health: http://127.0.0.1:8777/health"
