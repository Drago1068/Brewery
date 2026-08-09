# BrewingOS Increment 1 — NAS Persistence & Backup

## Git source of truth

```text
\\NazarioNAS\USB_3TB\BrewingOS   (mapped as B:\BrewingOS)
```

This external USB share holds **code and documentation**, not runtime database
files for production containers.

## Runtime persistent mounts

Configure via `.env` (see `.env.example`):

| Variable | Container path | Purpose |
|----------|----------------|---------|
| `BREWINGOS_POSTGRES_DATA` | `/var/lib/postgresql/data` | PostgreSQL data |
| `BREWINGOS_STORAGE` | `/BrewingOS/storage` | App file storage |
| `BREWINGOS_LOGS` | `/BrewingOS/logs` | Application logs |
| `BREWINGOS_BACKUPS` | `/BrewingOS/backups` | Logical DB dumps |

Recommended NAS **internal** paths when Compose runs on NazarioNAS (ADR-002 live layout):

```text
/volume1/docker/brewingos/data/postgres
/volume1/docker/brewingos/data/storage
/volume1/docker/brewingos/logs
/volume1/docker/brewingos/backups
```

Aspirational `/volume1/Apps/...` paths remain valid when that tree is creatable.

## Backup method (Increment 1)

```bash
docker compose --profile backup up -d backup
docker compose exec backup sh -c 'pg_dump -Fc > /BrewingOS/backups/brewingos-$(date +%Y%m%d).dump'
```

Restore:

```bash
docker compose exec -T backup pg_restore -d brewingos --clean --if-exists /BrewingOS/backups/<file>.dump
```

## Container replaceability

Containers are ephemeral. Recreating `backend` / `frontend` / `postgres`
containers must not destroy data as long as bind-mounted host paths remain.

## Docker + SMB caveat

The Git root lives on `\\NazarioNAS\USB_3TB\BrewingOS`. Docker Desktop cannot
reliably bind-mount that SMB path as application source. Compose therefore
**builds code into images** and only bind-mounts persistent data directories
(`postgres`, `storage`, `logs`, `backups`).

For live-reload development, clone/copy the repo to a local disk and use:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Sibling workload isolation

BrewingOS runtime must never mount or write:

```text
\\NazarioNAS\CODEX\**
\\NazarioNAS\docker\claude\**
\\NazarioNAS\docker\aegis*\**
\\NazarioNAS\docker\pos-platform\**
\\NazarioNAS\personal_folder\deployments\**
```

See [NAS_DEPLOYMENT.md](NAS_DEPLOYMENT.md) and [ADR-001-access-model.md](ADR-001-access-model.md).
