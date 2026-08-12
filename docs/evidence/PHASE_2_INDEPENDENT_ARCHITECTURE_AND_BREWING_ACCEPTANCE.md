# Phase 2 Independent Architecture and Brewing Acceptance

## Decision

`PASS`

Scope: `PHASE_2_BREWING_CORE`

Excluded scope: `PHASE_3_NOT_INCLUDED`

## Baseline

- Phase 1A source tag: `v0.1.0-phase1a`
- Phase 1A source commit: `d864bbd505cf7b7bb03a2652ebf1c86819aa48ee`
- Closure branch: `main`
- Phase 2 implementation baseline commit: `TO_BE_RECORDED_AFTER_BASELINE_COMMIT`
- Final accepted tag: `v0.2.0-phase2`
- Tag target: the evidence-complete Phase 2 closure commit

## Architecture Findings

- The deployable remains a modular monolith; no microservice or distributed-authority boundary was introduced.
- Four-layer conformance remains intact: platform infrastructure, brewing domain models, application orchestration, and HTTP/UI presentation remain separated.
- Authoritative brewing formulas remain in `packages/calculations`; React formats and displays persisted outputs but does not own calculations.
- PostgreSQL remains authoritative. Redis has no authoritative inventory, recipe, or calculation responsibility.
- ADR-0008 through ADR-0011 were reviewed against the implementation and accepted without discrepancy:
  - ADR-0008: canonical `g`, `L`, `degC`, `SG`, `SRM`, `ppm`, and `each` units; Decimal arithmetic; no intermediate rounding; presentation-only UI rounding.
  - ADR-0009: named Tinseth, Morey, ABV, pitch, carbonation, and unit-policy model identities are persisted with recipe versions.
  - ADR-0010: equipment, normalized inputs, authoritative outputs, and model versions are snapshotted; live equipment changes do not silently recalculate history.
  - ADR-0011: physical stock derives from append-only transactions; active reservations are distinct allocations with auditable zero-delta reservation/release entries.
- No Phase 3 fermentation execution, packaging, serving/menu, learning, sensory, competition, advanced analytics/AI, IoT, or deployment functionality is present.

### Application-service responsibility review

`apps/api/brewing_api/application/brewing_core.py` is a large Phase 2 orchestration facade with independently recognizable equipment/catalog, inventory, recipe calculation/versioning, availability, scaling, and substitution sections. A future split by use-case family would improve navigation before substantial Phase 3 expansion. Closure-time refactoring was not justified because:

- authoritative calculations are already isolated in `packages/calculations`;
- persistence entities remain in domain modules and HTTP contracts remain in presentation modules;
- ownership and transaction helpers are intentionally shared;
- responsibilities are sequentially grouped rather than materially tangled;
- behavior-preserving decomposition would enlarge the reviewed diff and regression surface without correcting a current defect.

Result: acceptable for the Phase 2 baseline; decomposition is recorded as technical debt, not a closure blocker.

## Brewing-Domain Findings

- Equipment profile assumptions are owned, validated, referenced, and snapshotted for historical reproducibility.
- Ingredient categories support fermentables, hops, yeast, water additions, adjuncts, finings, nutrients, and miscellaneous ingredients with extensible optional metadata.
- Selected hop-lot alpha acid overrides the catalog default and is preserved in the calculation path.
- Inventory is transaction-derived and append-only; transfers retain source/destination auditability.
- Reservations and releases are auditable and remain distinct from physical consumption.
- `Recipe` and `RecipeVersion` remain separate; clone/scale creates a new version and does not overwrite the original.
- A used recipe version remains protected by PostgreSQL immutability enforcement.
- Calculation snapshots preserve equipment, inputs, outputs, and model identities.
- Golden validation covers conversion, gravity/extract, expected OG/FG, apparent attenuation, ABV, efficiency, Tinseth IBU, Morey SRM, water volumes, strike temperature, yeast pitch, carbonation, mineral contribution, and scaling.
- Decimal arithmetic is authoritative and intermediate values are not rounded. UI formatting rounds only displayed results.
- Scaling is process-aware: batch volume is a base factor; fermentables compensate for source/target efficiency; salts follow recalculated total liquor; water and fixed losses/boil-off are recalculated from target equipment; hops and yeast use documented volume foundations. The engine does not multiply every field blindly.
- Availability returns `AVAILABLE`, `PARTIAL`, or `SHORTAGE` without mutating a recipe.
- Substitution relationships remain manual advisory metadata and always require brewer approval.

## Test Evidence

Exact-tree closure commands and actual results on 2026-08-12:

```powershell
docker compose run --rm api ruff check brewing_api tests /workspace/packages/calculations /workspace/database/migrations
```

Result: PASS, all checks passed.

```powershell
docker compose run --rm api pytest -q
```

Result: PASS, `21 passed, 3 skipped`. The skipped cases are PostgreSQL-only integration tests. One non-blocking Starlette TestClient deprecation warning recommends future `httpx2` adoption.

```powershell
docker compose exec -T -e TEST_USE_POSTGRES=1 api pytest -q tests/test_postgres_integrity.py tests/test_phase2_postgres_integrity.py
```

Result: PASS, `3 passed` with the same non-blocking TestClient warning.

```powershell
docker run --rm brewing-platform-web-closure npm test
docker run --rm brewing-platform-web-closure npm run lint
docker run --rm brewing-platform-web-closure npx tsc --noEmit
docker build --target build -t brewing-platform-web-closure -f infrastructure/docker/web.Dockerfile .
```

Result: PASS; Vitest `5 passed`, ESLint clean, TypeScript clean, and the Next.js production build completed successfully.

```powershell
docker compose --profile test run --rm --build e2e
```

Result: PASS, `2 passed`: the complete accepted Phase 1A Mash workflow and the complete Phase 2 Brewing Core workflow. Phase 1A coverage includes authentication, recipe/session creation, Mash start, persisted timer and browser refresh recovery, pH/gravity reminders and measurements, deterministic deviations, completion, journal, and planned-versus-actual display. Phase 2 coverage proves equipment -> ingredients -> inventory receipt -> recipe formulation -> calculation -> availability -> scaling -> cloned version -> original version unchanged.

```powershell
docker run --rm brewing-platform-web-closure npm audit
docker run --rm brewing-platform-e2e-closure npm audit
```

Result: PASS, zero known vulnerabilities in both dependency trees.

## Database Evidence

- Expected migration: `0002_phase2_brewing_core`.
- Alembic before and after round trip: `0002_phase2_brewing_core (head)`.
- Executed `alembic downgrade 0001_phase1a` followed by `alembic upgrade head`: PASS.
- Representative Phase 1A counts were compared before downgrade, at Phase 1A, and after re-upgrade. The vector `users,recipes,recipe_versions,brew_sessions,measurements,audit_events = 1,4,6,2,4,73` was unchanged: `PHASE1A_COUNTS_PRESERVED=True`.
- PostgreSQL tests prove recipe-version and completed-measurement immutability, inventory-ledger update rejection, transaction constraints, and migration-head identity.

## Inventory Integrity Evidence

- No authoritative `quantity_on_hand` field exists.
- Direct ledger update/delete is rejected by `inventory_ledger_immutable`.
- Purchase/return, consumption/waste, signed adjustment, transfer, reservation, and release projection rules are deterministic.
- Transfers require distinct source and destination locations and have zero global physical delta.
- Reservations reduce availability without changing on-hand quantity; releases append audit entries.
- Application commands reject debits or reservations exceeding available stock.
- Ingredient canonical-unit mismatches are rejected.
- Safety-stock states derive deterministically from available stock and the enabled threshold.
- Lot-specific hop alpha acid and cross-user identifier isolation are covered by backend tests.
- Reservation consumption remains intentionally deferred.

## Recipe History Evidence

- `Recipe` is the conceptual beer; `RecipeVersion` is the formulation snapshot.
- The Phase 2 E2E clone path creates version 2 and verifies version 1 retains its original batch volume and calculation document.
- Equipment and calculation assumptions are copied into each version, so later live profile changes do not silently rewrite historical values.
- Process steps and water targets are version-owned and cloned into the new formulation.

## Security and Artifact Evidence

- Repository scans found no `.env`, private keys, tokens, database dumps, test databases, logs, Playwright artifacts, `node_modules`, virtual environments, IDE state, or generated build directories in the worktree.
- `.env.example` contains secret placeholders plus documented non-secret local defaults/URLs only; no credential value is present.
- Secret-pattern file scanning found no suspicious credential-bearing file.
- Authentication and ownership remain server-side; automated tests prove a second user cannot list or use another user's equipment, ingredients, inventory identifiers, or recipe inputs.
- PostgreSQL and Redis have no host exposure; API and web bind only to `127.0.0.1` development ports.
- No public service exposure, NAS change, or production deployment occurred.

## Runtime Evidence

The disposable Docker environment reported PostgreSQL, Redis, FastAPI, and Next.js healthy. Runtime requests returned:

- `/health/live`: HTTP 200
- `/health/ready`: HTTP 200
- `/designer`: HTTP 200
- authenticated login: HTTP 200
- authenticated equipment profiles: HTTP 200
- authenticated ingredients: HTTP 200
- authenticated inventory balances: HTTP 200

The disposable environment was stopped with `docker compose down`; persistent volume data was not deleted.

## Known Limitations and Technical Debt

- Split the large Brewing Core application facade by use-case family before substantial future expansion if coupling begins to grow.
- Ingredient optional attributes use validated extensible JSON rather than fully typed category tables.
- Supplier/SupplierItem persistence exists without a dedicated management UI.
- Water chemistry is a deterministic contribution/target foundation, not an acid-base equilibrium or mash-pH predictor.
- Yeast pitch and priming sugar are documented planning foundations, not biological guarantees.
- Hop and yeast scaling use documented volume foundations; future validated alternatives require new model identities.
- Reservation consumption, purchasing automation, fermentation, packaging, serving/menu, learning, sensory, competition, advanced analytics/AI, IoT, and production deployment remain deferred.
- The FastAPI test client should migrate to `httpx2` in a later controlled maintenance change.

## Phase Boundary

`PHASE_3_NOT_AUTHORIZED`

`NAS_PRODUCTION_DEPLOYMENT_NOT_AUTHORIZED`

## Final Baseline

- Branch: `main`
- Phase 2 implementation baseline commit: `TO_BE_RECORDED_AFTER_BASELINE_COMMIT`
- Evidence-complete accepted tag: `v0.2.0-phase2`
- Tag target: this evidence-complete closure state

No Phase 3 work is authorized by this acceptance record.
