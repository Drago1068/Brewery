# Architecture Understanding Report

Status: reviewed before Phase 1 implementation on 2026-08-11.

## Product objective

The Brewing Platform is a private, single-user knowledge and execution system that preserves the lineage from a versioned recipe through brew-day observations and later improvement. Phase 1A proves only the recipe-to-completed-mash portion of that loop.

## Architecture layers and boundaries

The implementation is a modular monolith with four conforming layers:

1. Platform: identity, authorization, persistence, audit, logging, configuration, notifications, observability, and backup support.
2. Brewing domain: explicit recipe, brew-session, workflow, measurement, calculation, notification, and audit modules for this slice.
3. Application: use cases and versioned API orchestration; domain rules do not live in the UI.
4. Implementation: Next.js, FastAPI, PostgreSQL, Redis, Docker Compose, migrations, and tests.

Modules may collaborate through application services and domain events without circular dependencies. PostgreSQL is authoritative. Redis is non-authoritative support infrastructure only.

## MVP and deferred scope

Authorized work is the Phase 1 foundation and Phase 1A workflow: create a recipe and immutable version, start a session and Mash stage, persist a timer, issue pH and gravity reminders, record and compare measurements, record deviations, complete Mash, generate an automatic journal, and restore the active view after refresh.

Inventory workflows, the complete Recipe Designer and brew workflow, fermentation, packaging, serving/menu, learning, sensory, competition, analytics, advanced AI, branding, and IoT remain deferred.

## Security constraints

Management endpoints require server-side authentication and authorization. Secrets remain outside Git; only `.env.example` is committed. Credentials and API keys are never bundled into the frontend. Containers use isolated services, health checks, structured logs, and least-privilege application behavior. No public NAS exposure or production credential work is authorized.

## Data integrity rules

Identifiers are UUIDs and authoritative timestamps are UTC. Physical values carry explicit units. Targets, actuals, tolerances, variances, and deviation state remain distinct. A recipe version becomes immutable after a session uses it. Measurements on a completed stage cannot be silently updated; corrections are append-only and auditable. Schema evolution uses migrations.

## AI and inventory boundaries

AI is advisory only and is not implemented in Phase 1A. It cannot perform authoritative calculations or mutate recipes, measurements, history, or inventory. Future ingredient and packaged-product inventory must be ledger-based; Phase 1A does not implement inventory.

## Brew-day workflow and acceptance criteria

The session follows `PLANNED -> READY -> ACTIVE -> COMPLETED`, with `ABORTED` reserved. Mash has its own lifecycle and a server-persisted timer. Required pH and gravity measurements gate completion. Workflow actions emit timestamped journal and audit events. Acceptance requires an end-to-end run, accurate timer recovery after refresh/reconnect, persisted measurements, planned-vs-actual display, journal/audit evidence, passing automated tests, and no material architecture violation.

## Initialization selections

- Repository: `B:\brewing-platform`, an independent Git repository on the mapped UGREEN NAS volume.
- Development/runtime: local Docker Compose; no NAS configuration or public exposure changes.
- Backup support: PostgreSQL backup/restore commands target a configurable, Git-ignored `BACKUP_DIR`; the development default is `B:\brewing-platform-backups`. Off-device production backup remains an operational gate.
- Units for Phase 1A: temperature in degrees Fahrenheit (`degF`), acidity in `pH`, gravity in specific gravity (`SG`), and duration in integer seconds/minutes. All API and database values include or imply the schema-declared explicit unit.
- Runtime versions: Node.js 22 LTS container, Next.js 16.3.0, React 19.2.8, TypeScript 6.0.3, Python 3.13 container, FastAPI 0.141.1, SQLAlchemy 2.0.52, Alembic 1.19.1, and Pydantic 2.13.4. Versions are pinned and were checked against their package registries on 2026-08-11. TypeScript 7 was rejected during validation because it is outside the supported peer range of the current Next.js ESLint toolchain.
- Authentication: single-user opaque server session stored as an HTTP-only cookie; Argon2id password verification; bootstrap username and password are supplied only through environment variables. The API authorizes every management route.

No conflict with the accepted ADRs was found. These selections implement documented requirements without changing the approved architecture.
