# Epic 1 Security Notes

**Scope:** Epic 1 minimum security posture  
**Date:** 2026-08-09

## Implemented

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

## Explicit Epic 1 limitations

1. **No application login** — single-homebrewer `default_actor_id` (ADR-002). Access relies on Tailscale/loopback (ADR-001).
2. **Frontend serves Vite dev server in Docker** — production static/nginx packaging deferred (ADR-002 §E).
3. **Default example credentials** must be rotated before any shared/production use.
4. **CORS** allows configured origins; keep private until Cloudflare Access gate (future).

## Checklist before wider exposure

- [ ] Rotate `POSTGRES_PASSWORD` and `BREWINGOS_SECRET_KEY`
- [ ] Confirm Postgres has no host port publish
- [ ] Tailscale Serve dedicated to BrewingOS (do not overwrite POS routes)
- [ ] Production frontend image (Increment 7 follow-up / ops)
- [ ] Identity-aware external access only after ADR-001 later gate
