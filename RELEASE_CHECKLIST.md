# LEGALII Enterprise Release Checklist

## 0) Scope freeze
- [ ] Branch clean (`git status` reviewed)
- [ ] Version tag/changelog prepared
- [ ] Critical endpoints smoke-tested

## 1) Security baseline
- [ ] `LEGALII_REQUIRE_AUTH=true`
- [ ] `LEGALII_STRICT_MODE=true`
- [ ] `LEGALII_API_KEY` set to strong secret
- [ ] `LEGALII_TOKEN_SECRET` set to different strong secret
- [ ] `LEGALII_CORS_ORIGINS` restricted to known origins
- [ ] Audit log path writable and monitored (`enterprise/logs/audit.log`)
- [ ] Review log path writable (`enterprise/logs/review.log`)

## 2) Runtime checks
- [ ] `./scripts/legalii-enterprise-up.sh` passes preflight
- [ ] `GET /health` returns ok
- [ ] `GET /api/v1/system/config` reachable with admin key
- [ ] Login flow works (`POST /api/v1/auth/login`)
- [ ] Review flow works (`review-queue` + `review-resolve`)

## 3) Data safety
- [ ] End-to-end smoke scenario passes (`scripts/legalii-smoke.sh`)
- [x] Backup plan for `enterprise/data/*` defined (`scripts/legalii-backup.sh`)
- [x] Rotation/retention policy for logs defined (`scripts/legalii-retention.sh`)
- [ ] No sensitive test data in git

## 4) Deployment edge
- [ ] Reverse proxy + TLS configured (if internet exposed)
- [ ] Firewall restricts inbound ports
- [ ] Monitoring/alerting on container restarts and healthcheck failures

## 5) Sign-off
- [ ] Security sign-off
- [ ] Product sign-off
- [ ] Handoff doc updated (`HANDOFF_STATUS.md`)
