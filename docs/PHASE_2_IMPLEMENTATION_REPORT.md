# Phase 2 Implementation Report

## Executive summary

Phase 2 Brewing Core was implemented against accepted baseline tag `v0.1.0-phase1a` at commit `d864bbd505cf7b7bb03a2652ebf1c86819aa48ee`, passed independent architecture and brewing-domain review, and completed baseline-closure regression. Phase 3 has not begun.

## Delivered

- Owned equipment profiles with immutable historical snapshots.
- Category-aware ingredient catalog, lots, suppliers, and lot-specific hop alpha acid.
- Append-only transaction ledger, separate reservations, deterministic projections, locations, transfers, and safety stock warnings.
- Versioned recipe formulations, ingredient/use schedules, process and water foundations, persisted calculation/model snapshots.
- Decimal calculation engine: conversions, gravity/extract, attenuation/FG, ABV, efficiency, Tinseth IBU, Morey SRM, brewing water, strike temperature, yeast pitch, carbonation, minerals, and process-aware scaling.
- Availability states `AVAILABLE`, `PARTIAL`, and `SHORTAGE` without recipe mutation.
- Manual substitution candidates with impact/confidence metadata and mandatory brewer approval.
- Responsive Recipe Designer and clone-to-new-version workflow.
- Additive/reversible Alembic migration `0002_phase2_brewing_core` and ADRs 0008-0011.

## Verification evidence

- Ruff: PASS.
- Backend SQLite/API/domain/golden suite: 21 passed, 3 PostgreSQL-only skipped.
- PostgreSQL migration/integrity suite: 3 passed.
- Migration `0002 -> 0001 -> 0002` round trip: PASS.
- Frontend Vitest: 5 passed.
- ESLint: PASS.
- TypeScript and Next.js production build: PASS.
- Phase 1A browser regression: PASS.
- Phase 2 browser E2E: PASS; equipment → catalog → inventory → formulation → calculation → availability → scale/clone → original unchanged.
- Docker Compose configuration and four-service health: PASS; Alembic reported `0002_phase2_brewing_core (head)` and live/ready/designer routes returned HTTP 200.
- Web and E2E `npm audit`: PASS, zero known vulnerabilities.

These are the exact closure results for the accepted tree; any later source change requires a new regression and baseline.

## Security and architecture

All management routes retain authenticated HTTP-only sessions and server-side ownership checks. Unit/category/value validation is enforced at Pydantic, application, and PostgreSQL boundaries. PostgreSQL is authoritative; Redis has no inventory/calculation authority. Brewing rules remain outside React. Inventory and audit history are append-oriented.

Automated security cases prove a second authenticated user cannot list or use the first user's equipment, ingredients, inventory identifiers, or recipe-design inputs. Transaction debits cannot make available stock negative, arbitrary units are rejected, and PostgreSQL prevents ledger update/delete.

The modular monolith and four-layer boundary remain intact. No microservices, arbitrary unit injection, automatic substitutions, autonomous AI, or Phase 3 workflows were introduced.

## Known limitations and technical debt

- Ingredient optional attributes use validated extensible JSON rather than fully typed per-category tables.
- Supplier/SupplierItem persistence exists, but dedicated management UI/API is deferred.
- Water chemistry is contribution/target foundation only; no advanced acid-base equilibrium or mash-pH predictor.
- Yeast pitch and priming sugar outputs are planning foundations with documented fixed assumptions.
- Scaling hops and yeast uses volume-based foundations; future validated models can replace them through versioned model IDs.
- No purchasing automation, reservation consumption workflow, fermentation execution, packaging inventory, or production deployment.
- The FastAPI test client emits a dependency deprecation warning for future `httpx2` migration.

## Gate recommendation

**PASS / ACCEPTED PHASE 2 BASELINE.** Phase 3 remains a separate explicit authorization boundary.

## Stop

Implementation stops after Phase 2. Phase 3 requires explicit authorization following independent review.
