# Product Requirements v1.0

## Core User Experiences

### Learn
Structured lessons, quizzes, practical exercises, mastery tracking, contextual explanations, and AI tutoring.

### Design
Create recipes using style targets, ingredient calculations, equipment profile, water chemistry, process assumptions, and versioning.

### Plan
Confirm ingredient availability, identify shortages, suggest inventory substitutions, calculate purchase requirements, and respect safety stock.

### Brew
Run a guided brew-day workflow with timers, stage reminders, required measurements, notes, deviations, and automatic journal capture.

### Ferment
Track fermentation temperature, gravity, milestones, additions, attenuation, and packaging readiness.

### Package
Record kegging/canning/bottling, carbonation, packaging date, yield, location, and remaining quantity.

### Serve
Maintain current beer-on-hand inventory and publish a digital menu showing beers on tap and/or available in cans/bottles.

### Evaluate
Capture sensory observations, structured off-flavor descriptors, BJCP-style scores, and competition feedback.

### Improve
Compare planned vs actual performance, identify recurring process variation, evaluate recipe changes, and recommend next-version improvements.

## Inventory Requirements
- Ingredient master data.
- Lot-level inventory where relevant.
- Quantity on hand.
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
- Required/optional measurement prompts.
- Reminder escalation.
- Timestamped notes.
- Planned vs actual values.
- Variance thresholds.
- Corrective action suggestions.
- Automatic journal generation.
- Resume active brew after browser/device interruption.

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
Security, backup/recovery, mobile responsiveness, accessibility, testability, traceability, auditability, observability, deterministic calculations, reliable timers, and data portability.
