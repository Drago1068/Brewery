# BrewingOS Backup & Restore

## Principle

A backup is not proven merely because a dump file exists.

Required proof path:

**BACKUP → RESTORE INTO ISOLATED ENVIRONMENT → VERIFY DATABASE → VERIFY REPRESENTATIVE APPLICATION DATA**

## Backup (Compose profile)

```bash
cd /volume1/docker/brewingos/stack   # or your STACK_ROOT
docker compose --env-file /volume1/docker/brewingos/secrets/.env --profile backup up -d backup
docker compose --env-file /volume1/docker/brewingos/secrets/.env exec backup \
  sh -c 'pg_dump -Fc > /BrewingOS/backups/brewingos-$(date +%Y%m%d).dump'
```

Host backup directory is configured by `BREWINGOS_BACKUPS` (live default: `/volume1/docker/brewingos/backups`).

## Restore into an isolated environment

1. Create a separate Compose project / Postgres data directory (do **not** overwrite live data first).
2. Start an isolated Postgres with an empty data dir.
3. Restore:

```bash
docker compose exec -T backup \
  pg_restore -d brewingos --clean --if-exists /BrewingOS/backups/<file>.dump
```

4. Point a temporary backend at the isolated DB (or restore into a named test database).

## Verification checklist

After restore:

- [ ] `SELECT key, value FROM app_meta;` shows expected epic/increment/schema_version
- [ ] Representative brewery row present
- [ ] At least one equipment profile present
- [ ] Ingredient + lot + inventory_transactions history present
- [ ] Recipe + RecipeVersion + component snapshots present
- [ ] Backend `/health` and `/health/ready` OK against restored DB
- [ ] `/api/v1/meta` returns expected product metadata

## Persistence / container recreation

Containers are replaceable. Recreating `backend`/`frontend`/`postgres` containers must retain data when bind mounts remain:

- `BREWINGOS_POSTGRES_DATA`
- `BREWINGOS_STORAGE`
- `BREWINGOS_LOGS`
- `BREWINGOS_BACKUPS`

Manual persistence smoke (NAS):

```bash
curl -sS http://127.0.0.1:18182/api/v1/meta
docker compose restart backend
curl -sS http://127.0.0.1:18182/api/v1/meta
# Confirm brewery/recipes still list after recreate:
curl -sS http://127.0.0.1:18182/api/v1/brewery
```
