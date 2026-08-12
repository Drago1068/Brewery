# Architecture Charter

## Four Layers

### 1. Platform Architecture
Identity, authorization, persistence, audit, notifications, scheduling, file/object storage, AI orchestration, observability, configuration, backups.

### 2. Brewing Domain Architecture
Learning, Ingredients, Inventory, Equipment, Recipes, Brew Sessions, Fermentation, Packaging, Serving/Menu, Sensory, Competition, Analytics, AI Coach.

### 3. Application Architecture
Dashboard, Recipe Designer, Brew-Day Mode, Inventory, Cellar/Packaging, Digital Menu, Learning Center, Sensory/Competition, Administration.

### 4. Implementation Architecture
Frontend, backend, database, cache/jobs, Docker, NAS deployment, CI/CD, libraries.

## Governance
Lower architecture layers must conform to higher layers. Exceptions require an ADR.

## Initial Architecture Style
Modular monolith with explicit domain-module boundaries.

## Mandatory Cross-Cutting Rules
- Server-side authorization.
- Explicit units.
- UTC timestamps in storage; localized presentation.
- Append-only inventory transaction ledger.
- Immutable completed brew observations.
- No authoritative business calculation performed only by an LLM.
- Database migrations are mandatory for schema evolution.
- APIs are versioned where externally consumed.
