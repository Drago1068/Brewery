# Development Roadmap

This roadmap sequences the mandatory scope in the [Brewing Intelligence & Competition OS Master Plan](product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md). “Later” means phase-gated, not optional. Core Product V1 spans several development phases and must not be confused with Phase 1.

## Phase 0 — Architecture & Governance

Status: ACCEPTED

Charter, requirements, architecture, domain/data model, calculation specification, AI boundary, security, ADRs, scope governance, and agent handoff.

## Phase 1 — Platform Foundation

Status: ACCEPTED

Repository, local Docker stack, frontend/backend shells, PostgreSQL, Redis support boundary, configuration/secrets, migrations, identity, authorization, logging/audit, test infrastructure, and CI baseline.

## Phase 1A — Architecture-Proving Vertical Slice

Status: ACCEPTED

Create Recipe → Start Brew Session → Mash Timer → pH Reminder → Record pH → Mash Gravity Reminder → Record Gravity → Complete Mash → Planned-versus-Actual → Journal.

## Phase 2 — Brewing Core

Status: ACCEPTED — `v0.2.0-phase2`

Equipment profiles and snapshots, ingredients/lots/suppliers, ledger inventory and reservations, safety stock, Recipe Designer, versioning, deterministic calculations, process-aware scaling, availability, and manual substitution foundation.

## Phase 3 — Brew-Day OS

Status: ACCEPTED — `v0.3.0-phase3`

Complete stage-aware worksheet; multiple persistent timers; hop/addition schedules; required-data reminders; mash, post-mash, pre-boil, OG, knockout, volume, and temperature measurements; validation; planned-versus-actual deviations; voice-entry confirmation boundary; event log; photos/notes; automatic journal; and refresh recovery.

Normative gate: [Phase 3 Engineering and Acceptance Specification](specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md).

Acceptance record: [Phase 3 Formal Acceptance Record](evidence/PHASE_3_ACCEPTANCE.md).

## Phase 4 — Fermentation, Conditioning & Yeast

Status: ENGINEERING SPECIFICATION REVIEW CANDIDATE — AWAITING INDEPENDENT SPECIFICATION REVIEW AND EXPLICIT IMPLEMENTATION AUTHORIZATION

Gravity/temperature/pH tracking, fermentation curves, alerts, yeast lots and pitch history, milestones/additions, conditioning, readiness, and troubleshooting.

Normative gate: [Phase 4 Engineering and Acceptance Specification](specifications/PHASE_4_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md).

## Phase 5 — Quality, Packaging & Finished Beer

QA/QC, sanitation/CIP, calibration and maintenance foundations, oxygen/packaging exposure, stability, packaging sessions, carbonation, kegs, cans/bottles, package traceability, draft assets, taps, line cleaning, and consumption.

Gate: Core Product V1 grain-to-glass traceability and operating loop.

## Phase 6 — Inventory Intelligence, Purchasing & Operations

Reorder points and alerts, supplier lead times, demand forecasts, purchasing, freshness/waste, substitute simulation/compatibility, production calendars, competition deadlines, maintenance/calibration scheduling, and equipment-capacity planning.

## Phase 7 — Master Brewer Academy

Progressive curriculum, skill assessment, brewing science/mathematics, BJCP/style education, sensory training, fault identification, triangle testing, practical exercises, and contextual “Teach me why” instruction.

## Phase 8 — Advanced Recipe Experiments & Sensory

Sensory-target formulation, stronger style constraints, advanced water/formulation support, cost optimization, A/B and split-batch experiments, structured sensory, panels, BJCP-style scoresheets, and recipe iteration.

## Phase 9 — Competition, Branding & Digital Menu

AI-judge advisory workflow, judge-disagreement analysis, competition selection/calendar/entries/history/awards, beer naming, identity, logos, labels, tap badges, QR menu, and authoritative live package availability.

## Phase 10 — Brewer Knowledge Engine

Personal brewing profile, historical batch analysis, recipe/process/outcome correlations, experiment synthesis, evidence-ranked recommendations, intelligent substitutions, and future-batch guidance with explicit confidence and brewer approval.

## Release horizons

- **Core Product V1:** the trustworthy learn/plan → formulate → acquire → brew → ferment → package → trace → evaluate loop.
- **Advanced capabilities:** deeper inventory, operations, academy, experimentation, sensory, competition, and branding capabilities.
- **Future intelligence:** the Brewer Knowledge Engine and calibrated advisory analysis, introduced only after sufficient trusted evidence exists.
