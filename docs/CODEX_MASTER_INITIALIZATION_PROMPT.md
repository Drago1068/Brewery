# CODEX MASTER INITIALIZATION PROMPT

You are the implementation engineer for the Brewing Platform.

The repository architecture baseline is authoritative. Read every file in `docs/` before changing code.

## Objective
Initialize the project and implement only Phase 1 plus the Phase 1A architecture-proving vertical slice.

## Architectural Constraints
1. Use a modular monolith.
2. Preserve the documented four-layer architecture.
3. Do not introduce microservices.
4. PostgreSQL is the authoritative database.
5. Redis may support jobs/cache/timing coordination but may not become authoritative storage.
6. Authoritative brewing calculations must be deterministic and tested.
7. Completed brew observations are immutable/auditable.
8. Inventory is ledger-based when implemented.
9. AI cannot directly mutate authoritative history.
10. Schema changes use migrations.
11. Secrets never enter Git.
12. Significant architecture changes require an ADR and must stop for review before implementation.

## Initial Repository Target
apps/web
apps/api
packages/calculations
packages/shared-types
docs
database/migrations
infrastructure/docker
tests

Adapt structure where framework conventions demand it, but preserve logical module boundaries.

## Phase 1 Tasks
- initialize Git-safe project files
- Docker Compose development stack
- Next.js/TypeScript frontend
- FastAPI/Python backend
- PostgreSQL
- Redis
- environment configuration
- secrets template only; never real secrets
- health checks
- structured logging
- database migrations
- test harness
- CI-ready commands
- README runbook

## Phase 1A Vertical Slice
Implement:
1. Create a recipe with a name and mash target values.
2. Create a recipe version.
3. Start a brew session from that version.
4. Start the Mash stage.
5. Start and persist the Mash timer.
6. Trigger a pH measurement reminder.
7. Record mash pH.
8. Trigger a mash-gravity measurement reminder.
9. Record mash gravity.
10. Compare measurements with targets/tolerances.
11. Record deviation when outside tolerance.
12. Complete the Mash stage.
13. Create timestamped automatic journal events.
14. Display planned vs actual values in the UI.
15. Resume the active session correctly after browser refresh.

## Tests Required
- domain/unit tests
- calculation tests
- database/integration tests
- API tests
- timer recovery test
- measurement validation tests
- immutability/audit tests
- E2E browser test for the complete vertical slice

## Deliverables
- runnable repository
- migrations
- test results
- README
- architecture compliance report
- known issues
- proposed backlog items

## Stop Conditions
Stop and report without improvising if:
- existing repository content conflicts with this baseline;
- an architectural decision is required that is not covered;
- a security-sensitive credential decision is required;
- a migration threatens existing data;
- the chosen framework/version creates a material incompatibility.

Do not implement later roadmap phases during this initialization.
