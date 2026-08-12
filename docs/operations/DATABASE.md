# Database

PostgreSQL 17.6 is authoritative. Redis is non-authoritative and currently used only as a readiness-checked support boundary.

## Migrations

The API container runs `alembic upgrade head` before application startup. Manual commands:

```powershell
docker compose run --rm api alembic current
docker compose run --rm api alembic upgrade head
```

Migration `0001_phase1a` remains unchanged. Additive migration `0002_phase2_brewing_core` adds equipment, catalog, lots, ledger inventory, reservations, safety stock, recipe formulation, water targets, substitutions, and calculation snapshot columns. It is compatible with legacy recipe versions because new Phase 2 fields are nullable. Its downgrade removes only Phase 2 objects and was round-trip tested locally.

PostgreSQL triggers protect used recipe versions, completed-stage measurements, and every inventory transaction from update/delete. Inventory corrections are new `ADJUSTMENT` entries; reservation/release audit entries do not change physical stock.

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
