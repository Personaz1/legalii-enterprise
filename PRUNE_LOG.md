# Prune Log (legalii-core)

Date: 2026-02-08
Branch: `legalii-core`

## Moved to `_pruned/`
- `apps/` (mobile/native app surfaces)
- `Swabble/`
- `extensions/` (full extension set; broad channel scope removed)
- Docs sections:
  - `docs/platforms`
  - `docs/channels`
  - `docs/nodes`
  - `docs/automation`
  - `docs/experiments`
  - `docs/plugins`
  - `docs/zh-CN`

## Skills reduced to legal-focused minimal set
Kept in `skills/`:
- `github`
- `healthcheck`
- `nano-pdf`
- `openai-whisper-api`
- `summarize`

Moved to `_pruned/skills/`:
- all remaining skills

## Additional cuts (2026-02-08)
- Removed public demo surface from runtime (`legalii-kit/demo` moved to `_pruned/legalii/demo`)
- Replaced demo UI entrypoint with API-first enterprise service root

## Reason
Reduce surface area, maintenance burden, and unrelated capabilities for a legal-first product.
