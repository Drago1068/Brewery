# E2A-1 — BrewEvent Deferment (SUPERSEDED)

**Status:** Superseded by [`E2A2_ENTRY_AMENDMENT.md`](E2A2_ENTRY_AMENDMENT.md)  
**Date:** 2026-08-09  
**Superseded:** 2026-08-09 (pre–E2A-2 architecture amendment)

## Resolution (locked)

1. Canonical `brew_events` ships in migration **`006_brew_day_events_stage_machine`**, before stage-transition implementation.  
2. E2A-1 interim use of `audit_events` for `PLAN_CREATED` / `READINESS_ACKNOWLEDGED` remains historical evidence only.  
3. Migration `006` **backfills** canonical `brew_events` from durable BrewPlan acknowledgement fields and matching `audit_events` (option **B**).  
4. After `006`, new Brew-Day domain mutations write `brew_events` directly in the same transaction.  
5. `audit_events` must **not** be used as a temporary substitute for E2A-2 Brew-Day domain events.

See the entry amendment for schema sketch, indexes, backfill algorithm, duplicate protection, and locked `START_SESSION`.

## Historical note

E2A-1 deferred `brew_events` because the prior packaging placed them with timers. That packaging is amended; domain ADR semantics were never changed.
