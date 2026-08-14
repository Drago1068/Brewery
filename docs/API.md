# API

The external management API is versioned under `/api/v1`. All routes except login and health checks require the authenticated HTTP-only `brewing_session` cookie and enforce ownership server-side.

## Identity

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/csrf` returns the synchronizer CSRF token for an authenticated browser session.

## Recipes

- `POST /api/v1/recipes` creates `Recipe` and immutable `RecipeVersion` v1.
- `GET /api/v1/recipes` lists the authenticated user's latest versions.

## Brewing core

- `POST|GET /api/v1/equipment-profiles`
- `POST|GET /api/v1/ingredients`
- `POST|GET /api/v1/suppliers` and `POST /api/v1/suppliers/{id}/items`
- `POST|GET /api/v1/ingredient-lots` (creation also appends the initial purchase)
- `POST|GET /api/v1/inventory/locations`
- `POST /api/v1/inventory/transactions`
- `GET /api/v1/inventory/balances`
- `POST /api/v1/inventory/reservations`
- `POST /api/v1/inventory/reservations/{id}/release`
- `PUT /api/v1/inventory/safety-stock`
- `POST /api/v1/recipe-designs` calculates and persists version 1.
- `GET /api/v1/recipe-designs/{version_id}` returns the persisted snapshot and current availability.
- `POST /api/v1/recipe-designs/{version_id}/clone` scales and saves a new immutable version.
- `POST /api/v1/ingredient-substitutions`
- `GET /api/v1/ingredients/{id}/substitution-candidates?required_quantity=...`

All identifiers are ownership-scoped. Quantities use the ingredient's canonical `g`, `L`, or `each` unit; mixed-unit writes are rejected. Substitution candidates are advisory and always require brewer approval.

## Brew sessions

- `POST /api/v1/brew-sessions` creates a planned session from a recipe version, materializes the Phase 3 execution snapshot, and snapshots targets.
- `GET /api/v1/recipe-versions/{id}/phase3-plan-preview` returns the deterministic plan preview hash and addition assignments.
- `POST /api/v1/brew-sessions/{id}/start` progresses `PLANNED -> READY -> ACTIVE`.
- `POST /api/v1/brew-sessions/{id}/pause` and `/resume` pause/resume the session and `ACTIVE_TIME` timers.
- `POST /api/v1/brew-sessions/{id}/abort` aborts the session with a required reason.
- `GET /api/v1/brew-sessions/active` restores the active session after refresh/device reconnect.
- `GET /api/v1/brew-sessions/{id}` returns persisted planned values, stages, timers, measurements, deviations, reminders, additions, notes, and journal.
- `POST /api/v1/brew-sessions/{id}/mash/start` persists Mash and its timer.
- `POST /api/v1/brew-sessions/stages/{stage_id}/start|skip|extend|repeat|return|complete`
- `POST /api/v1/brew-sessions/stages/{stage_id}/measurements` records a process observation.
- `POST /api/v1/brew-sessions/measurements/{id}/corrections` appends an auditable correction.
- `POST /api/v1/brew-sessions/reminders/{id}/acknowledge` acknowledges a reminder without completing it.
- `POST /api/v1/brew-sessions/timers/{id}/pause|resume|complete|cancel|acknowledge|replace|extend`
- `POST /api/v1/brew-sessions/{id}/requirements/{requirement_id}/additions` records an AdditionEvent with zero inventory effect.
- `POST /api/v1/brew-sessions/{id}/addition-events/{id}/corrections` appends `phase3-addition-correction-v1`.
- `POST /api/v1/brew-sessions/{id}/requirements/{requirement_id}/waivers` appends `phase3-waiver-v1`.
- `POST /api/v1/brew-sessions/{id}/notes` and `/attachments` add notes/photos.
- `POST /api/v1/brew-sessions/{id}/pitch-handoff` records the yeast-pitch handoff fact.
- `GET /api/v1/brew-sessions/{id}/journal|completion-audit|export`
- `POST /api/v1/brew-sessions/voice/proposals` parses an untrusted voice draft and never mutates Brew-Day state.

Browser mutations require `X-CSRF-Token` plus a same-origin `Origin`/`Referer`. Retryable mutations accept `operation_id` under `phase3-operation-v1`.

Interactive OpenAPI documentation is available at `http://127.0.0.1:18100/api/docs` while the stack is running.
