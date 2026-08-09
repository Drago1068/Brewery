# EPIC 2A FREEZE — Core Guided Brew Day

**Status:** FINAL ACCEPTED / FROZEN  
**Acceptance date:** 2026-08-09  
**Accepted baseline commit:** `ef4876eda62435ec58bdcab90c1dc3c514433101`

---

## Freeze summary

Epic 2A — Core Guided Brew Day is frozen at the accepted baseline above.

Tip documentation commit that records the E2A-6 review SHA may exist after the baseline; architectural and product acceptance is pinned to:

`ef4876eda62435ec58bdcab90c1dc3c514433101`

Schema version: **009**  
Migrations present through `009_fermentation_handoffs`. **No migration 010.**

Governing ADRs (accepted, immutable without new ADR / architecture amendment):

| ADR | Title |
|-----|--------|
| [ADR-004](ADR-004-brew-day-domain-stage-machine.md) | Brew-Day domain & stage machine |
| [ADR-005](ADR-005-measurement-integrity-provenance.md) | Measurement integrity & provenance |
| [ADR-006](ADR-006-brew-timers-offline-idempotency.md) | Brew timers & offline idempotency |

Final review package: [EPIC_2A_E2A6_FINAL_REVIEW_PACKAGE.md](EPIC_2A_E2A6_FINAL_REVIEW_PACKAGE.md)

---

## Frozen architecture

Treat the following as accepted architecture. Future changes require an explicit ADR or approved architecture amendment.

* BrewPlan from immutable ACTIVE/LOCKED RecipeVersion
* Ready-to-Brew acknowledgement behavior
* BrewSession state machine
* Ordered Epic 2A stage model
* Append-only BrewEvents
* Integer `BrewSession.version` OCC
* Idempotency ledger and replay semantics
* History-first measurement architecture
* `MeasurementRecord` as projection
* `MeasurementObservationHistory` as scientific history
* `MeasurementStatusHistory` as lifecycle history
* PENDING / CAPTURED / MISSED / WAIVED
* HIGH / MEDIUM / LOW confidence
* Timer timestamp authority
* Read-only timer GET
* Explicit timer elapsed observation
* Timers never controlling process state
* Separate Brew-Day audit dimensions
* No overall Brew Score
* Explicit CLOSED → HANDED_OFF
* No automatic fermentation handoff
* Planned and measured values never conflated
* Minimum offline queue / idempotent replay model

---

## Final verification snapshot

### Frontend

* **10** tests passed
* TypeScript build clean (`tsc -b`)

### Backend

* **167** passed
* **1** skipped

### Persistence (PostgreSQL restart)

Recorded from the E2A-6 live journey:

* BrewSession restored as **HANDED_OFF** after PostgreSQL restart
* BrewEvents restored
* Measurement observation history restored
* Timer restored
* Fermentation handoff restored

Evidence marker: `E2A6_PERSISTENCE_OK` (`backend/scripts/e2a6_live_journey_persist.py`)

### Schema

* Schema version: **009**
* Confirmed: **no migration 010** exists

---

## Known accepted limitations

Do not “fix” these by silently expanding scope:

* No Playwright browser automation in CI yet
* Offline queue is single-browser / `localStorage`
* BrewAction checklist remains lightweight
* Environment may expose API on configured port rather than Compose default
* No Epic 2B equipment-specific workflows
* No Epic 3 FermentationSession
* No Redis / workers / CRDT

---

## Explicit Epic 2B boundary

**Do not begin Epic 2B** under this freeze.

Epic 2B (equipment-aware workflow expansion, BIAB-specific redesign, three-vessel expansion, custom stage templates, commercial production planning, etc.) requires a new approved architecture / implementation handoff.

---

## Explicit Epic 3 boundary

**Do not begin Epic 3** until a new approved architecture / implementation handoff is issued.

Out of scope until then:

* FermentationSession
* Fermentation diary / observations
* Terminal-gravity logic
* Dry-hop / cold crash / conditioning execution
* Packaging / sensory
* Any claim that Epic 2 handoff equals fermentation readiness

The Epic 2A `fermentation_handoffs` row remains an immutable **boundary stub** only.

---

## Freeze protocol

1. Product/architecture acceptance pinned to `ef4876eda62435ec58bdcab90c1dc3c514433101`.
2. Schema frozen at **009**.
3. ADR-004 / ADR-005 / ADR-006 govern behavior.
4. Changes to frozen architecture require ADR or approved amendment **before** implementation.
5. Next epic work starts only from a new authorized handoff.

---

EPIC 2A FROZEN — READY FOR NEXT EPIC
