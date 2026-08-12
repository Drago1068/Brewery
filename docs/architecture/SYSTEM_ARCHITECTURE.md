# System Architecture

## Proposed Baseline
Frontend: Next.js + TypeScript
Backend: FastAPI + Python
Database: PostgreSQL
Cache/Jobs: Redis
Packaging/Runtime: Docker
Host: UGREEN NAS
Remote Access: secure tunnel infrastructure
Testing: unit + integration + API + browser E2E

Technology selections require final validation during repository initialization.

## Logical Modules
- identity
- brewing_profile
- equipment
- ingredients
- inventory
- recipes
- calculations
- brew_sessions
- workflow
- measurements
- fermentation
- packaging
- serving_menu
- sensory
- competition
- learning
- analytics
- ai_coach
- notifications
- audit

## Event Architecture
Use application/domain events inside the modular monolith. Initial events include:

RECIPE_VERSION_CREATED
BREW_SESSION_STARTED
BREW_STAGE_STARTED
BREW_STAGE_COMPLETED
BREW_MEASUREMENT_DUE
BREW_MEASUREMENT_RECORDED
BREW_VARIANCE_DETECTED
INVENTORY_RESERVED
INVENTORY_CONSUMED
INVENTORY_ADJUSTED
INVENTORY_BELOW_SAFETY_STOCK
FERMENTATION_MEASUREMENT_DUE
FERMENTATION_COMPLETED
BEER_PACKAGED
KEG_TAPPED
PACKAGE_DEPLETED
MENU_AVAILABILITY_CHANGED
SENSORY_EVALUATION_RECORDED

## Reliability
Brew-day timer state is persisted server-side so the active session can recover after client refresh/reconnect.

## AI Boundary
The AI layer consumes domain data and deterministic calculation results. It does not directly mutate authoritative brewing history without explicit application commands and validation.
