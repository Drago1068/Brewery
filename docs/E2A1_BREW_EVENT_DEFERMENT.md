# E2A-1 — BrewEvent Deferment (Architecture Note)

**Status:** Documented limitation for E2A-1 (not an ADR redesign)  
**Date:** 2026-08-09  
**Related:** ADR-004 §C/N, ADR-006, migration order 005 → 006 → 007 → 008

## Conflict

ADR-004 requires distinct append-only event rows for `PLAN_CREATED` and
`READINESS_ACKNOWLEDGED` in the same transaction as BrewPlan creation.

Approved migration order places `brew_events` in **`007_brew_day_timers_events`**,
not in `005`. Creating `brew_events` in E2A-1 would deviate from the locked
migration order.

## E2A-1 resolution (no throwaway history)

1. **Immutable BrewPlan columns** store readiness status, checks snapshot, and
   acknowledgement metadata (`readiness_acknowledged`, `_at`, `_by`, note).
   These columns are never rewritten after create.
2. **Distinct Epic 1 `audit_events` rows** are written in the same transaction:
   - `PLAN_CREATED`
   - `READINESS_ACKNOWLEDGED` (YELLOW/RED only)
3. No temporary mutable ack table is introduced.

Acknowledgement audit facts are therefore durable without inventing history that
will be discarded.

## E2A-2 expectation

When migration `007` lands:

- Emit canonical `BrewEvent` rows for new brew-day operations.
- Preserve E2A-1 `audit_events` rows (do not delete).
- Optionally backfill `BrewEvent` from BrewPlan ack columns / audit rows for
  plans created before `007` — decision required before E2A-2 implementation.

## Decision required before E2A-2

Choose one:

| Option | Description |
|--------|-------------|
| A | Dual-write `audit_events` + `brew_events` going forward; leave historical audit as-is |
| B | Backfill `brew_events` from E2A-1 BrewPlan columns / audit for PLAN_CREATED and READINESS_ACKNOWLEDGED |
| C | Treat `brew_events` as session-scoped only; keep plan-level ack exclusively on BrewPlan + audit |

No production redesign of ADR-004 event semantics is implied; this is packaging
order reconciliation only.
