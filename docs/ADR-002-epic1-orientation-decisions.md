# ADR-002 — Epic 1 Orientation Decisions (PO-authorized)

**Status:** Accepted (Epic 1 interim decisions)  
**Date:** 2026-08-08  
**Amended:** 2026-08-09 — lock production auth/deployment as **explicitly deferred** (must not become long-term architecture by default)  
**Context:** Epic 1 handoff 1.2 orientation reported decisions required before domain implementation. Product Owner authorized proceeding.

## Decisions

### A. Authentication (Epic 1 interim only)

Single-homebrewer operation with `default_actor_id` (`local-brewer`) recorded on auditable writes. Access isolation remains ADR-001 (private Tailscale / loopback).

**Deferred (post–Epic 1 / production hardening — not optional forever):** full application identity (login / IAM). Epic 1 acceptance of “no login” is valid **only** for the private single-user NAS stage. It must **not** be treated as the long-term production security architecture. Introduce application auth before shared users, multi-operator use, or any exposure beyond ADR-001’s private gate.

### B. Canonical NAS runtime path

Accept the live layout as operational truth:

```text
/volume1/docker/brewingos/stack
/volume1/docker/brewingos/data/postgres
/volume1/docker/brewingos/data/storage
/volume1/docker/brewingos/logs
/volume1/docker/brewingos/secrets/.env
/volume1/docker/brewingos/backups
```

Preferred `/volume1/Apps/...` remains aspirational when sudo/admin creates it. Environment variables remain the configuration mechanism.

### C. Brewing formula methodologies

Deferred until before Increment 5. Domain increments 2–4 must not invent authoritative calculation results.

### D. RecipeVersion historical snapshot

When Recipe schema lands (Increment 4): snapshot calculation-critical ingredient attributes onto `RecipeVersion*` rows at save/lock so ingredient-library edits cannot rewrite historical meaning.

### E. Frontend packaging (development-grade for Epic 1)

**Epic 1 accepted posture:** Vite development server image in Compose is acceptable for **private NAS bring-up only**.

**Explicitly deferred past Epic 1 (Increment 7 did not close this):** multi-stage production static/nginx (or equivalent) frontend image. Do **not** promote the Vite-dev Compose service to “production packaging” by silence or convenience. Production-grade frontend packaging requires a deliberate post–Epic 1 ops/security task (or earlier if exposure increases).

See also `docs/SECURITY_EPIC1.md` — “Not the long-term production architecture.”

### F. Increment 1 baseline

Treat existing infrastructure as Increment 1 foundation. Domain work begins at Increment 2. Commits remain PO-directed.

## Consequences

- Increment 2 may proceed with brewery/equipment APIs and UI.
- Authorization is brewery-scoped server-side once multi-brewery records exist; Epic 1 still assumes one primary homebrewer.
- Formula work remains blocked pending a future ADR (resolved by ADR-003 for Increment 5).
- Epic 1 sign-off **does not** approve Vite-dev + no-login as permanent production deployment/security architecture; those remain open deferred items tracked in `docs/SECURITY_EPIC1.md`.
