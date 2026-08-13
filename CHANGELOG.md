# Changelog

## Unreleased — master-plan governance

- Locked the expanded Brewing Intelligence & Competition OS architecture as mandatory, phase-gated product scope.
- Separated Core Product V1, Advanced Capabilities, and Future Intelligence delivery horizons.
- Established the Brewing Data Core, deterministic calculation engine, and AI orchestration boundary without authorizing Phase 3 implementation.
- Added the documentation-only Phase 3 Brew-Day OS engineering and acceptance gate, including explicit Phase 4–10 anti-leakage controls; Phase 3 implementation remains unauthorized.
- Added the independent-review master prompt that binds review to the exact specification, requires full requirement/acceptance traceability, and prohibits implementation or silent specification edits.

## 0.2.0-phase2 - 2026-08-12

- Added owned equipment profiles and immutable recipe equipment snapshots.
- Added category-aware ingredients, lots with hop-specific alpha acid, suppliers, and supplier items.
- Added append-only ledger inventory, independent reservations, transfers, safety stock, and deterministic projections.
- Added Recipe Designer APIs/UI, persisted calculation snapshots, availability states, manual substitutions, and clone-to-new-version scaling.
- Expanded the authoritative Decimal calculation package for conversions, extract, OG/FG, attenuation, ABV, efficiency, Tinseth IBU, Morey color, water volumes, strike temperature, pitch, carbonation, minerals, and process-aware scaling.
- Added reversible migration `0002_phase2_brewing_core`, ADRs 0008-0011, backend/golden/PostgreSQL/frontend/E2E tests, and Phase 2 domain documentation.
- Preserved the Phase 1A workflow, passed independent architecture and brewing-domain review, and closed the reproducible Phase 2 accepted baseline.
- Stopped before Phase 3; fermentation, packaging, serving/menu, learning, sensory, competition, advanced analytics/AI, IoT, and production deployment remain excluded.

## 0.1.0-phase1a - 2026-08-11

- Initialized the independent `B:\brewing-platform` Git repository.
- Added the Phase 1 Docker, Next.js, FastAPI, PostgreSQL, Redis, authentication, logging, health, migration, audit, test, CI, and backup foundations.
- Added the Phase 1A versioned-recipe-to-completed-Mash workflow.
- Added persisted timers and reminders, validated measurements, deterministic variance checks, deviations, immutable-history enforcement, automatic journal events, and responsive planned-versus-actual UI.
- Added unit, API, PostgreSQL integration, frontend, and browser E2E evidence.
- Completed an isolated restore of the accepted PostgreSQL dump and verified migration state, core schema, constraints, integrity triggers, representative records, and a read-only relational smoke query.
- Re-ran the exact-tree closure regression, dependency audits, runtime health checks, and authenticated API smoke validation.
- Recorded independent architecture acceptance and closed the Phase 1/1A baseline for tagging.
- Stopped before Phase 2 for independent architecture review.

Phase 3 remains explicitly unauthorized.
