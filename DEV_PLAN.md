# LEGALII Development Plan (to production)

## Target
Ship deployable LEGALII product for local machine and VPS:
- enterprise positioning
- secure defaults
- usable UI
- repeatable deployment

## Milestones

### M1. Product skeleton (today)
- [x] establish LEGALII codebase and prune non-legal surfaces
- [x] legal rules engine + report API
- [ ] enterprise UI shell
- [ ] API auth guard + audit logging
- [ ] local + server deploy profiles

### M2. Workflow hardening
- [ ] structured case intake (JSON/PDF/image)
- [ ] versioned rulesets by case type
- [ ] report export (html/pdf/json)
- [ ] error handling + observability

### M3. Enterprise readiness
- [ ] tenant/workspace concept
- [ ] roles (admin/lawyer/assistant)
- [ ] backup and retention policy hooks
- [ ] installer script (local + vps)

### M4. Launch package
- [ ] product docs (admin/user/security)
- [ ] deployment checklist
- [ ] pilot runbook

## Definition of Done
1. `./scripts/legalii-enterprise-up.sh` starts product on clean machine
2. UI accessible, branded, with product descriptions
3. API protected by key in production mode
4. Audit log written for analysis actions
5. Works local and on standard VPS (docker-compose)
