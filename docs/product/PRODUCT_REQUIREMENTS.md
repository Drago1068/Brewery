# Product Requirements v1.0

This document refines the mandatory capabilities in the [Brewing Intelligence & Competition OS Master Plan](BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md). Delivery is split into Core Product V1, Advanced Capabilities, and Future Intelligence; deferral to a later horizon does not make a capability optional.

## Core User Experiences

### Learn
Master Brewer Academy with progressive curriculum, brewing science and mathematics, BJCP/style education, sensory and fault-identification training, triangle testing, practical exercises, skill assessment, mastery tracking, contextual “teach me why” explanations, and bounded AI tutoring.

### Design
Translate sensory targets into equipment-aware recipes using style constraints, ingredient calculations, water chemistry, mash/boil/hop/yeast formulation, cost optimization, process assumptions, scaling/upscaling, immutable versioning, and controlled A/B or split-batch experiments.

### Plan
Confirm lot-level availability and freshness, reserve inventory, identify shortages, simulate compatible substitutions, calculate purchase requirements, respect safety stock/reorder points/lead times, forecast demand, and reduce waste.

### Brew
Run a stage-aware interactive worksheet with concurrent and automatic addition timers, required-data and pH/gravity/volume reminders, voice-assisted confirmed entry, validated planned-versus-actual measurements, photos, notes, deviations, audit history, and timestamped journal capture.

### Ferment
Track gravity, temperature, pH, curves, milestones, additions, attenuation, yeast pitch calculations and history, alerts, conditioning, troubleshooting, and packaging readiness.

### Package
Record kegging/canning/bottling, oxygen exposure, carbonation, packaging quality and stability checks, packaging date, yield, location, and remaining quantity with batch traceability.

### Serve
Maintain keg/can/bottle inventory, draft-system and tap assignments, line-cleaning reminders, consumption, and a QR-capable digital menu grounded in live authoritative availability.

### Evaluate
Capture structured sensory observations, off-flavor descriptors, BJCP-style scoresheets, triangle tests, AI-judge advice, judge disagreement, competition selection/calendar/entries/history/awards, and resulting iteration evidence.

### Improve
Use the Brewer Knowledge Engine and personal brewing profile to compare planned vs actual performance, analyze historical batches and experiment history, identify recipe-performance correlations, evaluate changes, and recommend evidence-ranked future-batch improvements.

### Assure Quality and Operate
Manage QA/QC, sanitation/CIP, equipment maintenance, instrument calibration, microbiology/contamination awareness, brewing/fermentation/packaging/competition calendars, purchasing, scheduling, and equipment-capacity planning.

### Brand and Publish
Generate brewer-approved beer names, identity concepts, logos, labels, and tap badges while publishing digital and QR menus whose availability comes only from authoritative finished-beer inventory.

## Inventory Requirements
- Ingredient master data.
- Lot-level inventory where relevant.
- Quantity on hand derived from the append-only inventory ledger.
- Unit and conversion.
- Supplier and cost.
- Storage location.
- Best-by/expiration where relevant.
- Safety-stock threshold.
- Reorder point.
- Inventory transaction history.
- Recipe reservation/commitment support.
- Substitution engine constrained by ingredient role, style impact, quantity, and inventory availability.
- Purchase list generation.
- Reorder alerts, supplier lead times, demand forecasts, freshness controls, and waste-minimization guidance.
- Substitution simulation with compatibility score, process/flavor impact, confidence, and explicit approval.

## Packaged Beer Requirements
- Keg inventory.
- Can/bottle inventory.
- Package size.
- Fill date.
- Batch/recipe lineage.
- Estimated remaining volume/count.
- Serving status.
- Storage location.
- Tap assignment.
- Menu visibility.
- Depletion/empty status.

## Digital Beer Menu Requirements
Display:
- beer name
- style
- ABV
- optional IBU
- availability format: tap/can/bottle
- serving size where relevant
- tasting description
- optional artwork/logo
- availability status

## Brand/Creative Requirements
AI may propose beer names, descriptions, and logo concepts from brewer-provided themes and recipe characteristics. Generated brand assets remain separate from authoritative recipe data.

## Recipe Scaling
Recipes must scale by target finished volume while considering:
- equipment profile
- brewhouse efficiency
- losses
- ingredient utilization
- hop utilization effects where applicable
- yeast requirements
- water volume
- mineral additions
- packaging target

## Brew-Day Requirements
- Workflow state machine.
- Stage timers.
- Multiple concurrent timers where needed.
- Automatic hop and addition timers.
- Required/optional measurement prompts.
- Reminder escalation.
- Timestamped notes.
- Confirmed voice data entry, photos, and attachments.
- Planned vs actual values.
- Variance thresholds.
- Corrective action suggestions.
- Automatic journal generation.
- Resume active brew after browser/device interruption.

## Quality and Operations Requirements
- QA/QC plans and evidence linked to batches and packages.
- Sanitation/CIP records, equipment maintenance, and line-cleaning schedules.
- Instrument calibration history and due reminders.
- Contamination-awareness guidance without fabricating microbiological evidence.
- Packaging quality, stability testing, oxygen exposure, and carbonation controls.
- Brewing, fermentation, packaging, purchasing, maintenance, calibration, and competition calendars.
- Brew scheduling and equipment-capacity planning.

## Intelligence Requirements
- Maintain a personal brewing profile, historical-batch evidence, experiment history, and recipe-performance correlations.
- Recommendations must cite relevant evidence, assumptions, confidence, and uncertainty.
- AI may explain, tutor, diagnose, simulate, synthesize, recommend, and create drafts.
- Deterministic application services must calculate, validate, record, authorize, and enforce rules.
- AI cannot autonomously control brewery equipment or silently change authoritative records.

## Required Measurement Examples
- source water or brewing water values where available
- mash-in temperature
- mash temperature
- mash pH
- pre-boil gravity
- pre-boil volume
- post-boil gravity/OG
- post-boil volume
- pitch temperature
- fermentation temperature
- gravity during fermentation
- FG
- package volume
- carbonation where tracked

## Nonfunctional Requirements
Security, server-side authorization, explicit units, UTC storage, backup/restore/repair, mobile responsiveness, accessibility, testability, traceability, provenance, auditability, observability, explainable AI, deterministic calculations, reliable timers, and data portability.
