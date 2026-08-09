# ADR-002 — Epic 1 Orientation Decisions (PO-authorized)

**Status:** Accepted  
**Date:** 2026-08-08  
**Context:** Epic 1 handoff 1.2 orientation reported decisions required before domain implementation. Product Owner authorized proceeding.

## Decisions

### A. Authentication (Epic 1)

Single-homebrewer operation with `default_actor_id` (`local-brewer`) recorded on auditable writes. Access isolation remains ADR-001 (private Tailscale / loopback). Full identity auth deferred until external access is gated.

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

### E. Frontend production packaging

Defer multi-stage static/nginx image until Increment 7 (or earlier if exposure increases). Vite dev image acceptable for private NAS bring-up.

### F. Increment 1 baseline

Treat existing infrastructure as Increment 1 foundation. Domain work begins at Increment 2. Commits remain PO-directed.

## Consequences

- Increment 2 may proceed with brewery/equipment APIs and UI.
- Authorization is brewery-scoped server-side once multi-brewery records exist; Epic 1 still assumes one primary homebrewer.
- Formula work remains blocked pending a future ADR.
