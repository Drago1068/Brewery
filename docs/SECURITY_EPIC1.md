# Epic 1 Security Notes

**Scope:** Epic 1 **minimum / development-grade** security & deployment posture  
**Date:** 2026-08-09  
**Amended:** 2026-08-09 — explicit non-promotion of interim controls to production architecture  

## Not the long-term production architecture

Epic 1 deployment is **development-grade**, which is **acceptable for Epic 1** and **must remain explicitly deferred** for production:

| Interim Epic 1 control | Status | Must not become… |
|------------------------|--------|------------------|
| No application login (`default_actor_id`) | Accepted for private single-user NAS (ADR-002 §A) | Permanent production IAM / auth architecture |
| Network isolation only (Tailscale / loopback) (ADR-001) | Accepted for current private stage | Sole long-term production security model |
| Vite **dev** server as the Compose frontend | Accepted for private NAS bring-up (ADR-002 §E) | Production frontend packaging |

**Non-promotion rule:** Review acceptance of Epic 1 must **not** be read as approving these three items as the finished production security/deployment architecture. Closing them requires explicit PO-authorized follow-on work (and ADR updates where access model changes).

## Implemented (Epic 1)

| Control | Status |
|---------|--------|
| Secrets excluded from Git (`.env` gitignored; `.env.example` only) | Yes |
| Postgres not published on host by default | Yes (`brewingos-data` internal network) |
| Loopback binds for API/UI ports by default | Yes (`127.0.0.1:18181/18182`) |
| Server-side validation via Pydantic schemas | Yes |
| Authorization not trusted to frontend alone | Yes (network isolation + ADR-001; actor recorded server-side) |
| Safe error handling on readiness/health paths | Yes |
| Alembic migrations versioned | Yes (`001`–`004`) |
| Inventory/calculation/readiness do not weaken isolation | Yes |
| Audit events for brewery/equipment/inventory/recipe lifecycle | Foundation yes |

## Explicit Epic 1 limitations (deferred production hardening)

1. **No application login** — single-homebrewer `default_actor_id` (ADR-002 §A). Access relies on Tailscale/loopback (ADR-001). **Deferred:** real login / IAM before shared or production use.
2. **Frontend serves Vite dev server in Docker** — production static/nginx packaging **deferred past Epic 1** (ADR-002 §E; Increment 7 did not deliver it).
3. **Default example credentials** must be rotated before any shared/production use.
4. **CORS** allows configured origins; keep private until Cloudflare Access gate (ADR-001 later).

## Deferred production track (post–Epic 1 — do not drop)

Track these as open hardening work until PO closes them:

- [ ] Production frontend image (static build + nginx or equivalent; retire Vite-dev service for any production-labeled deploy)
- [ ] Application authentication / authorization (replace sole reliance on `default_actor_id` + network isolation)
- [ ] Rotate `POSTGRES_PASSWORD` and `BREWINGOS_SECRET_KEY` before shared use
- [ ] Confirm Postgres has no host port publish
- [ ] Tailscale Serve dedicated to BrewingOS (do not overwrite POS routes)
- [ ] Identity-aware external access only after ADR-001 later gate (Cloudflare Access MFA or equivalent)
- [ ] Explicit PO decision that environment may be labeled **production** (Epic 1 Compose stack is not that label by default)

## Checklist before wider exposure

Complete the deferred production track items above **before** shared users, multi-operator use, or any exposure beyond private Tailscale/loopback.
