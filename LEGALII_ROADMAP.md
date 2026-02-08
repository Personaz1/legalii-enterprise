# LEGALII Roadmap

## Goal
Build a legal-focused private AI platform: local-first, confidentiality-first, deployable out-of-the-box.

## Phase 0 — Slim Core (in progress)
- Create LEGALII repository and prune to legal core
- Create branch `legalii-core`
- Remove non-essential product surfaces (mobile apps, broad extensions, non-legal skills)
- Keep core agent runtime + gateway + legal toolchain

## Phase 1 — Rebrand
- Rename product in UI/docs to `LEGALII`
- Add legal positioning text (privacy/compliance)
- Keep CLI stable under `legalii` command.

## Phase 2 — Legal Pack (MVP)
- Case intake (JSON/PDF/image)
- Checklist engine for case types (asilo, arraigo, nacionalidad)
- Risk flags + timeline inconsistency checks
- Export report (JSON/MD/HTML/PDF)

## Phase 3 — Local LLM Mode
- Default to local model provider where available
- Explicit data-boundary indicator: "Data stays on this machine"
- Optional cloud model with explicit consent flags

## Phase 4 — Distribution
- One-command bootstrap installer
- Docker compose profile for solo lawyer / small firm
- First-run setup wizard (storage path, backups, retention)

## Acceptance criteria (commercial)
1. Install + first report in < 15 minutes
2. No cloud dependency for core analysis path
3. Clear privacy story usable in sales
4. Repeatable deployment on laptop and low-cost VPS
