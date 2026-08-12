# API

The external management API is versioned under `/api/v1`. All routes except login and health checks require the authenticated HTTP-only `brewing_session` cookie and enforce ownership server-side.

## Identity

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`

## Recipes

- `POST /api/v1/recipes` creates `Recipe` and immutable `RecipeVersion` v1.
- `GET /api/v1/recipes` lists the authenticated user's latest versions.

## Brew sessions

- `POST /api/v1/brew-sessions` creates a planned session from a recipe version and snapshots targets.
- `POST /api/v1/brew-sessions/{id}/start` progresses `PLANNED -> READY -> ACTIVE`.
- `GET /api/v1/brew-sessions/active` restores the active session after refresh/device reconnect.
- `GET /api/v1/brew-sessions/{id}` returns persisted planned values, stage, timer, measurements, deviations, reminders, and journal.
- `POST /api/v1/brew-sessions/{id}/mash/start` persists Mash and its timer.
- `POST /api/v1/brew-sessions/stages/{stage_id}/measurements` records pH or gravity.
- `POST /api/v1/brew-sessions/measurements/{id}/corrections` appends an auditable correction.
- `POST /api/v1/brew-sessions/stages/{stage_id}/complete` validates required observations and completes Mash/session.

Interactive OpenAPI documentation is available at `http://127.0.0.1:18100/api/docs` while the stack is running.

