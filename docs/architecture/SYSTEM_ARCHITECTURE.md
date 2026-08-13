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
- equipment_assurance
- ingredients
- inventory
- suppliers_purchasing
- recipes
- experiments
- calculations
- brew_sessions
- workflow
- measurements
- fermentation
- yeast_management
- conditioning
- quality_sanitation
- packaging
- finished_beer
- draft_system
- serving_menu
- branding
- sensory
- competition
- learning
- academy
- operations_scheduling
- analytics
- knowledge_engine
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
The Brewing Data Core owns authoritative facts and provenance. Deterministic services calculate, validate, record, authorize, and enforce rules. The AI Orchestration Layer consumes authorized domain data and deterministic results to explain, tutor, diagnose, simulate, synthesize, create drafts, and recommend. It does not directly mutate authoritative brewing history or operational state without explicit validated application commands.

The complete mandatory capability map and delivery horizons are governed by the [Brewing Intelligence & Competition OS Master Plan](../product/BREWING_INTELLIGENCE_AND_COMPETITION_OS_MASTER_PLAN.md).
