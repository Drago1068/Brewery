# Increment 1 — Infrastructure Foundation

**Status:** Complete (verified)

## Delivered

- Docker Compose: `postgres`, `backend`, `frontend`, optional `backup`
- PostgreSQL 16 with healthcheck; host port not published by default
- NAS-configurable bind mounts for DB, storage, logs, backups
- Alembic migration `001_initial_foundation` (`app_meta`)
- API liveness `/health` and readiness `/health/ready` (Postgres + storage)
- Meta endpoint `/api/v1/meta`
- Frontend foundation status screen
- Backend + frontend unit tests
- Persistence verified after backend container recreate

## Verification results (2026-08-08)

| Check | Result |
|-------|--------|
| `docker compose config` | OK |
| Backend pytest (in image) | 5 passed |
| Frontend vitest | 1 passed |
| Migration `001` | Applied on startup |
| `/health` | ok |
| `/health/ready` | ok (postgres + storage) |
| `/api/v1/meta` | epic=1, infrastructure=active |
| Backend recreate | `app_meta` retained |

## Environment notes

- Git root: `\\NazarioNAS\USB_3TB\BrewingOS` (`B:\BrewingOS`)
- Windows Docker Desktop: runtime data uses local paths under
  `C:\Users\Drago\AppData\Local\BrewingOS-dev\data\*` because SMB USB bind
  mounts are unreliable for Postgres. On-NAS deploy should use `/volume1/Apps/...`.
- Source is baked into images (no SMB source bind mounts).

## Explicitly deferred to later increments

Brewery, equipment, ingredients, inventory, recipes, calculations, readiness.
