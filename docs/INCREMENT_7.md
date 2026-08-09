# Increment 7 — Integration & Hardening

**Status:** Complete for Epic 1 review handoff

## Delivered

- Domain-level primary journey integration test (inventory → recipe → calculate → readiness)
- Invalid calculation non-fabrication test
- Security notes (`docs/SECURITY_EPIC1.md`)
- Backup/restore verification doc (`docs/BACKUP_RESTORE.md`)
- Epic 1 Implementation Review Package (`docs/EPIC_1_IMPLEMENTATION_REVIEW.md`)
- Increment marker set to **7**; readiness module active

## Verification

| Check | Result |
|-------|--------|
| Backend pytest | Run in Increment 7 |
| Frontend `tsc` | Run in Increment 7 |
| `docker compose config` | CI job |
| Migrations | `001`–`004` additive |

## Explicitly deferred / out of scope

- Epic 2 BrewPlan / BrewSession execution
- Playwright browser E2E harness (API/domain journey covered; UI E2E deferred)
- **Production-grade deployment/security** (must stay deferred — do not promote by silence):
  - Production nginx/static frontend image (ADR-002 §E; Vite-dev remains Epic 1 only)
  - Application login / IAM (ADR-002 §A; network isolation is interim per ADR-001)
  - Cloudflare Access / identity-aware edge (ADR-001 later gate)
- Automated restore-into-isolated-env CI job (documented procedure)

## Stop

Do **not** begin Epic 2. Await independent architecture review + Human Product Owner approval.

Do **not** treat Epic 1 Compose (Vite-dev + no login + Tailscale/loopback) as the long-term production architecture — see `docs/SECURITY_EPIC1.md`.
