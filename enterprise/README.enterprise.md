# LEGALII Enterprise (On-Prem)

## Quick start
1. `cd ..` (repo root)
2. `./scripts/legalii-enterprise-up.sh`
3. Open `http://localhost:8777/health`

The startup script runs preflight checks for Docker, compose, env files, auth flags and data/log directories.

## Security baseline
- Cloud models disabled by default
- Auth required in enterprise mode
- Strict legal mode enabled
- CORS is configurable via `LEGALII_CORS_ORIGINS`
- Audit logging enabled (`enterprise/logs/audit.log`)
- Review logging enabled (`enterprise/logs/review.log`)
- Container hardening: read-only FS, dropped caps, no-new-privileges

## Intended use
- Private legal case preprocessing
- Completeness checks and risk flags
- Structured report generation for legal teams

## Release gate
Before production deployment, complete `RELEASE_CHECKLIST.md` from repo root.


## Operations
- Backup now: `./scripts/legalii-backup.sh`
- Apply retention: `./scripts/legalii-retention.sh`
- End-to-end smoke: `./scripts/legalii-smoke.sh`
