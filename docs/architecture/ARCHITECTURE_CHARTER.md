# Architecture Charter

## Four Layers

### 1. Platform Architecture
Identity, authorization, Brewing Data Core, persistence, audit, notifications, scheduling, file/object storage, deterministic calculation engine, AI orchestration, observability, configuration, backups, restore, and repair.

### 2. Brewing Domain Architecture
Learning/Academy, Ingredients/Lots/Suppliers, Inventory/Purchasing, Equipment/Maintenance/Calibration, Recipes/Experiments, Brew Sessions, Fermentation/Yeast/Conditioning, Quality/Sanitation, Packaging/Finished Beer/Draft, Sensory/Competition, Operations/Scheduling, Branding/Menu, Analytics/Knowledge Engine, AI Coach.

### 3. Application Architecture
Dashboard, Recipe Designer and Experiment Workbench, Brew-Day Mode, Fermentation, Inventory/Purchasing, Quality/Equipment Assurance, Cellar/Packaging/Draft, Operations Calendar, Digital Menu/Brand Studio, Master Brewer Academy, Sensory/Competition, Knowledge Engine, Administration.

### 4. Implementation Architecture
Frontend, backend, database, cache/jobs, Docker, NAS deployment, CI/CD, libraries.

## Governance
Lower architecture layers must conform to higher layers. Exceptions require an ADR.

The [master plan](../product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md) is the authoritative capability scope. Capabilities may be phase-gated but not silently removed or reclassified as optional.

## Initial Architecture Style
Modular monolith with explicit domain-module boundaries.

## Mandatory Cross-Cutting Rules
- Server-side authorization.
- Explicit units.
- UTC timestamps in storage; localized presentation.
- Append-only inventory transaction ledger.
- Immutable completed brew observations.
- No authoritative business calculation performed only by an LLM.
- AI recommends and reasons; deterministic software calculates, validates, records, and enforces rules.
- AI actions that would change authoritative state require application validation, authorization, provenance, and explicit approval where applicable.
- Database migrations are mandatory for schema evolution.
- APIs are versioned where externally consumed.
