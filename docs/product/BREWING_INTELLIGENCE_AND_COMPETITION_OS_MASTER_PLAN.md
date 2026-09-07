# Brewing Intelligence & Competition OS Master Plan

## Authority and product boundary

This is the authoritative long-range product scope for the Brewing Platform, hereafter the **Brewing Intelligence & Competition OS**.

Every capability listed here is committed master-plan scope. Assignment to an advanced or intelligence horizon means sequenced, not optional or removed. Implementation still requires explicit phase authorization, acceptance criteria, migrations where needed, tests, documentation, and an architecture gate.

The latest accepted implementation baseline is Phase 4, tag `v0.4.0-phase4`. Earlier accepted tagged baselines remain immutable, including Phase 3 `v0.3.0-phase3` and Phase 2 `v0.2.0-phase2`. This plan does not independently authorize Phase 5 or NAS production deployment.

## Product architecture

The system has three foundational responsibilities:

1. **Brewing Data Core** — authoritative ownership, recipes and versions, equipment assumptions, ingredient lots, ledger inventory, execution and fermentation observations, package lineage, quality records, sensory evidence, competition records, learning progress, audit history, and provenance.
2. **Deterministic Calculation Engine** — unit conversion, validation, brewing mathematics, inventory projection, process calculations, comparison, scoring rules, and other reproducible computations. Inputs, outputs, model identities, units, and rounding policies must be explainable and versioned.
3. **AI Orchestration Layer** — bounded tutoring, explanation, diagnosis, synthesis, simulation, creative assistance, and recommendations grounded in authorized platform data and deterministic outputs.

The governing boundary is:

> AI recommends and reasons. Deterministic software calculates, validates, records, and enforces rules.

AI may not silently mutate recipes, replace ingredients, alter inventory, overwrite history, fabricate measurements or sensory evidence, or present uncertain inference as a deterministic result.

## Delivery horizons

The horizons distinguish sequencing and maturity, not required from optional scope.

### Horizon A — Core Product V1

Core Product V1 closes the trustworthy grain-to-glass operating loop:

Learn and plan → formulate → acquire/reserve → brew → ferment → package → trace → evaluate → improve

It includes the accepted Phase 0–2 foundations plus complete guided Brew-Day execution; fermentation and conditioning; packaging and finished-beer traceability; core QA/QC, sanitation, calibration, oxygen/carbonation, and maintenance records; operational calendars and reminders; inventory purchasing/reorder foundations; Master Brewer Academy foundations; and structured sensory foundations.

Core Product V1 is a release horizon delivered through multiple development phases. It is not the same as “Phase 1.”

### Horizon B — Advanced Brewing and Competition Capabilities

This horizon deepens optimization, experimentation, service, sensory, competition, and creative operations: sensory-target formulation, controlled A/B and split-batch experiments, advanced water and formulation support, inventory forecasting and substitute simulation, richer quality and stability workflows, full cellar/draft/menu operations, advanced sensory and competition management, capacity planning, and branding assets.

### Horizon C — Future Intelligence

Future Intelligence is mandatory product direction but depends on sufficient trusted history and calibrated evaluation: the Brewer Knowledge Engine, personal brewing profile, historical batch analysis, recipe-performance and process-outcome correlations, experiment synthesis, intelligent substitution simulation, AI-assisted judging, judge-disagreement analysis, competition selection, and evidence-ranked future-batch recommendations.

Intelligence remains advisory, cites evidence and assumptions, exposes uncertainty, and never becomes autonomous brewery control or silent authoritative mutation.

## Mandatory capability architecture

### 1. Learning — Master Brewer Academy

- Progressive curriculum and skill assessment.
- Brewing science and brewing mathematics.
- Ingredient, process, equipment, water, yeast, fermentation, packaging, quality, and stability education.
- BJCP style and competition education.
- Sensory vocabulary, sensory training, fault identification, and triangle testing.
- Practical exercises linked to recipes, brew sessions, fermentation records, and evaluations.
- Contextual **Teach me why** instruction throughout operational workflows.
- Progress, evidence, confidence, and mastery records in the Brewing Data Core.

### 2. Recipe Design and Experimentation

- Sensory-target-to-recipe translation and style/BJCP constraints.
- Equipment-aware formulation and immutable equipment/calculation snapshots.
- Process-aware recipe scaling and production upscaling.
- Water profiles, mineral and acid foundations, mash/boil/hop/yeast formulation, fermentation foundations, carbonation, and packaging targets.
- Cost calculation and constrained cost optimization.
- Immutable recipe versioning and full formulation lineage.
- Controlled A/B and split-batch experiment hypotheses, variable control, assignment, results, and comparison.
- Explicit distinction between predicted, planned, measured, inferred, and sensory values.

### 3. Brew-Day Execution

- Interactive brew worksheet with a stage-aware workflow/state machine.
- Multiple persistent timers and automatic hop/addition timers.
- Required-data reminders and escalation.
- Mash temperature/pH, post-mash gravity, pre-boil gravity/volume, OG, knockout, and other authorized measurement prompts.
- Voice-assisted entry routed through validation and explicit confirmation.
- Planned-versus-actual values, deterministic deviations, and corrective-action guidance.
- Measurement units, instrument, method, timestamp, provenance, and correction lineage.
- Brew-day audit, timestamped event log, photos, notes, and reconnect recovery.

### 4. Fermentation and Conditioning

- Gravity, temperature, and pH tracking with fermentation curves.
- Yeast inventory/lot, pitch calculations, pitch history, and reuse lineage where authorized.
- Deterministic alerts, additions, milestones, conditioning, readiness, and troubleshooting.
- No claim of exact biological prediction; AI diagnosis remains advisory.

### 5. Inventory, Suppliers, and Purchasing

- Grain, hop, yeast, adjunct, water-addition, fining, nutrient, and miscellaneous inventory.
- Lots, locations, transfers, reservations, releases, consumption, returns, adjustments, and waste through an append-only ledger.
- Safety stock, reorder points, supplier lead times, demand forecasts, and automatic reorder alerts.
- Supplier items, purchasing plans/orders, receipts, costs, and price history.
- Freshness, expiration, storage-condition foundations, and waste minimization.
- Inventory-aware substitutions with quantity conversion, process/flavor impact, simulation, compatibility scoring, confidence, and mandatory brewer approval.
- No automatic replacement or purchasing without an explicit authorized command.

### 6. Quality, Sanitation, and Equipment Assurance

- QA/QC plans, checkpoints, specifications, deviations, dispositions, and corrective actions.
- Sanitation/CIP procedures and execution/verification records.
- Equipment maintenance schedules, history, and readiness.
- Instrument calibration schedules, standards, results, expiry, and measurement-validity impact.
- Microbiology and contamination-awareness records and guidance.
- Packaging quality, carbonation, seams/closures where applicable, stability testing, and cold-side oxygen/exposure tracking.

### 7. Finished Beer, Cellar, Draft, and Serving

- Traceability from package to recipe version, ingredients/lots, brew, fermentation, and quality evidence.
- Keg and can/bottle inventory with package size, fill date, quantity, storage, depletion, and disposition.
- Draft-system assets, tap assignment, line identity, line-cleaning reminders/history, and readiness.
- Carbonation targets, measurements, adjustments, and history.
- Consumption/depletion tracking without invented precision.

### 8. Sensory and Competition

- Structured sensory evaluation, controlled vocabulary, provenance, serving conditions, and blind mode.
- BJCP-style scoresheets and style-relative evaluation.
- Fault identification, triangle tests, panels, repeats, and disagreement capture.
- AI judge as labeled advisory analysis; no fabricated judge evidence.
- Human and AI judge-disagreement analysis.
- Competition selection, calendar, deadlines, entries, history, awards, and feedback.
- Traceable recipe iteration based on sensory and competition results.

### 9. Operations and Scheduling

- Brewing, fermentation, conditioning, packaging, serving, competition, purchasing, maintenance, and calibration calendars.
- Brew scheduling, conflicts, dependencies, reminders, and equipment-capacity planning.
- Availability and lead-time checks against planned production.
- No autonomous production scheduling without brewer approval.

### 10. Branding and Digital Experience

- Beer names, descriptions, brand identity, logos, labels, and tap badges.
- Digital and QR-code beer menus.
- Live keg/can/bottle availability from authoritative inventory.
- Creative assets remain separate from recipe, batch, quality, and inventory facts.
- Published factual claims must come from validated platform records.

### 11. Intelligence — Brewer Knowledge Engine

- Personal brewing profile from explicit preferences, demonstrated practices, and accepted observations.
- Historical analysis across recipe, equipment, ingredients/lots, execution, fermentation, package, sensory, and competition evidence.
- Recipe-performance and process-outcome correlations with sample-size and confidence disclosure.
- Experiment registry and synthesis across A/B and split-batch trials.
- Evidence-ranked future recipe, process, quality, competition, inventory, and learning recommendations.
- Clear separation of fact, calculation, observation, inference, recommendation, and uncertainty.

## Mandatory cross-cutting controls

Every capability must preserve server-side authorization; explicit units; UTC storage; append-only or versioned history; observation provenance; immutable recipe and batch lineage; deterministic rules outside the LLM; explainable AI and approval gates; PostgreSQL authority and migrations; accessible responsive interfaces; calculation/domain/database/API/frontend/browser tests; observability, backup, restore, repair, and portability; and a separate authorization/evidence gate for NAS deployment.

## Phase governance

- Appearance in this plan does not authorize implementation.
- Every phase requires explicit authorization, bounded scope, acceptance criteria, security review, tests, evidence, and a stop gate.
- Completed tagged baselines are immutable.
- Deferred means sequenced, not removed.
- Maintain architectural compatibility without building speculative schemas far ahead of an authorized vertical slice.

## Current status and next boundary

- Phase 0: accepted architecture/governance foundation.
- Phase 1 and Phase 1A: accepted platform and architecture-proving Mash slice.
- Phase 2: accepted Brewing Core baseline, tag `v0.2.0-phase2`.
- Phase 3: accepted Brew-Day OS, tag `v0.3.0-phase3`; formal record [Phase 3 Formal Acceptance Record](../evidence/PHASE_3_ACCEPTANCE.md). The Phase 3 specification file retains its original in-document status wording because its exact bytes are bound by that record. No additional Phase 3 specification freeze is required.
- Phase 4: accepted and formally closed Fermentation and Conditioning OS, tag `v0.4.0-phase4`; records [Phase 4 Formal Specification Acceptance](../evidence/PHASE_4_FORMAL_SPECIFICATION_ACCEPTANCE.md) and [Phase 4 Formal Implementation Acceptance](../evidence/PHASE_4_FORMAL_IMPLEMENTATION_ACCEPTANCE.md).
- Phase 5: not authorized.
- NAS production deployment: not authorized.

Nothing in this master plan independently authorizes Phase 5 implementation or NAS production deployment.
