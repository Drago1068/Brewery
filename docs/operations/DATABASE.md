# Database

PostgreSQL 17.6 is authoritative. Redis is non-authoritative and currently used only as a readiness-checked support boundary.

## Migrations

The API container runs `alembic upgrade head` before application startup. Manual commands:

```powershell
docker compose run --rm api alembic current
docker compose run --rm api alembic upgrade head
```

Migration `0001_phase1a` creates only Phase 1/1A tables. PostgreSQL triggers prevent mutation/deletion of a recipe version used by a brew session and prevent mutation/deletion of measurements belonging to a completed stage. Corrections append a new measurement linked by `correction_of_id` and generate audit/journal events.

## Backup

The development destination defaults to `B:\brewing-platform-backups` and may be overridden with `BACKUP_DIR`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\docker\backup-postgres.ps1
```

The result is a PostgreSQL custom-format dump outside the repository. An off-device encrypted destination and scheduled restore drill remain deployment gates.

## Restore

Restore is destructive to current development objects and requires typing `RESTORE`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\docker\restore-postgres.ps1 -BackupFile 'B:\brewing-platform-backups\brewing-YYYYMMDD-HHMMSS.dump'
```

`-ExecutionPolicy Bypass` applies only to that child process and does not change the workstation policy.

After restore, restart the API, check `/health/ready`, and execute the integration and browser suites.
