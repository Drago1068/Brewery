# Architecture Compliance Report

Accepted baseline: `v0.1.0-phase1a` (`d864bbd505cf7b7bb03a2652ebf1c86819aa48ee`)

Assessment date: 2026-08-11
Decision boundary: Phase 2 review candidate; stop before Phase 3.

Architecture review was subsequently accepted. Closure and restore evidence is recorded in `docs/evidence/PHASE_1A_INDEPENDENT_ARCHITECTURE_ACCEPTANCE.md`.

## Implemented

- Independent Git repository and CI-ready monorepo structure.
- Docker Compose stack with healthy web, API, PostgreSQL, and Redis services; host bindings are restricted to `127.0.0.1`.
- Next.js/TypeScript responsive recipe and Brew-Day surfaces with loading, validation, error, and accessible interaction states.
- FastAPI modular monolith with versioned API, configuration validation, structured JSON logging, standard domain errors, authentication, and ownership authorization.
- Alembic migration for users/sessions, recipes/versions, brew sessions/stages/timers, measurements, deviations, reminders, journal events, and audit events.
- Recipe/version creation, session state progression, Mash start, authoritative persisted timer, reminder reconciliation, pH/gravity capture, deterministic comparisons, deviations, completion gates, automatic journal, planned-versus-actual view, and refresh recovery.
- Append-only measurement correction endpoint and PostgreSQL triggers protecting used recipe versions and completed-stage measurements.
- Git-ignored custom-format PostgreSQL backup plus confirmation-gated restore helper.
- GitHub Actions baseline for backend, PostgreSQL integration, frontend, and E2E checks.

Phase 2 adds owned equipment, category-aware ingredients/lots, append-only ledger inventory and independent reservations, safety stock, immutable recipe calculation snapshots, process-aware scaling, availability, manual substitutions, and a responsive Recipe Designer. PostgreSQL remains authoritative and the calculation package owns all brewing formulas.

## Tests and evidence

Executed locally against the candidate:

- `ruff check`: PASS.
- Backend SQLite/domain/API suite: PASS, 21 passed and 3 PostgreSQL-only tests skipped as designed.
- PostgreSQL migration/integrity suite: PASS, 3 passed. It verified Alembic head and exercised recipe, measurement, and inventory immutability triggers.
- Frontend Vitest suite: PASS, 5 passed.
- Frontend ESLint: PASS.
- Next.js production build and TypeScript compilation: PASS.
- Playwright Phase 1A and Phase 2 browser flows: PASS, 2 passed. They prove timer refresh recovery and the complete Brewing Core workflow through immutable scaling/cloning.
- Docker Compose validation: PASS.
- Runtime health: PASS for PostgreSQL, Redis, API, and web; `/health/live`, `/health/ready`, and `/login` returned success.
- npm audit for web and E2E packages: PASS, zero known vulnerabilities.
- PostgreSQL backup: PASS. A 37,767-byte custom-format dump was created at `B:\brewing-platform-backups\brewing-20260811-221207.dump`, and `pg_restore --list` validated its catalog.

The FastAPI test client emits a dependency deprecation warning recommending the future `httpx2` client; it does not affect current test results.

## ADR conformance

- ADR-0001: one deployable API modular monolith; no microservices.
- ADR-0002: platform capabilities, brewing-domain modules, application use cases, HTTP/UI presentation, and implementation infrastructure remain separated.
- ADR-0003: historical corrections append records and audit/journal events; PostgreSQL prevents silent updates after Mash completion.
- ADR-0004: variance/tolerance comparisons live in the deterministic `packages/calculations` code and have golden/edge tests.
- ADR-0005/ADR-0011: inventory derives from immutable transactions; reservations are independent allocations with auditable zero-delta ledger events.
- ADR-0006: the timer start, duration, pause fields, status, and completion are stored in PostgreSQL; the UI reconstructs display state and E2E proves refresh recovery.
- ADR-0007: public menu work remains deferred and no public endpoint was introduced.
- ADR-0008: canonical SI-oriented units and boundary conversion prevent mixed-unit calculations.
- ADR-0009: formula/model identifiers make Tinseth, Morey, ABV, pitch, and carbonation assumptions explicit.
- ADR-0010: each recipe version snapshots equipment, inputs, outputs, models, and unit policy.

## Security

Secrets remain external to source control. Management routes require server-side opaque sessions and ownership checks. Passwords use Argon2id; only salted token digests are persisted. Cookies are HTTP-only and SameSite=Lax, with secure-cookie configuration available for TLS. Database/cache services remain internal, and exposed development routes bind only to loopback. Mutation actions generate structured audit records.

## Deviations

There are no material deviations from the approved architecture. Dedicated host ports `18100`/`18101` replace the conventional `8000`/`3000` defaults because port `8000` was already occupied. TypeScript 6.0.3 was selected after TypeScript 7 failed the supported peer-range check for the current Next.js ESLint toolchain. Patched Vitest and Playwright releases replaced initially selected vulnerable versions before acceptance.

## Known issues and technical debt

- An actual restore was not executed because it replaces current database objects; only dump/catalog validation was performed.
- NAS deployment, TLS/private access, secure-cookie mode, off-device encrypted backup, and restore drills remain deployment gates.
- The bootstrap password creates the initial user but does not rotate an existing user's password when the environment value changes.
- SameSite cookies provide the current local CSRF boundary; explicit anti-CSRF tokens should be reviewed before any broader deployment surface.
- Redis is wired, isolated, and health-checked but has no authoritative or workflow responsibility in Phase 1A.
- Actual Mash temperature capture is truthfully shown as not recorded; Phase 1A requires only pH and gravity observations.
- Timer pause fields exist but pause/resume behavior is deferred.
- OpenAPI-derived frontend types, durable CI browser artifacts, and the `httpx2` test-client migration are backlog candidates.
- The GitHub Actions workflow is authored but has not run on a remote Git host.

## Recommended next step

Phase 2 gate recommendation: **PASS / READY FOR INDEPENDENT REVIEW**, not authorization for Phase 3 and not NAS-production readiness.

The reviewer should inspect the migration/trigger strategy, authentication/session boundary, module dependency direction, timer/reminder rules, mobile Brew-Day interaction, and backup/restore plan. Any requested correction should remain within Phase 1/1A until the gate is formally accepted.

## Proposed backlog after approval

1. Execute and document a disposable-database restore drill and encrypted off-device backup design.
2. Add explicit CSRF protection and administrator credential-rotation flow.
3. Generate shared TypeScript clients/types from OpenAPI.
4. Decide whether timer pause/resume and Mash-temperature capture belong in the next authorized milestone.
5. Publish CI artifacts and dependency/container scan results.

## Stop

Implementation stops here. Phase 3 has not begun and requires explicit authorization after review.
