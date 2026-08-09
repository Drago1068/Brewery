# Brewing Intelligence & Competition OS

Homebrewer-first brewing application. Epic 1 — Brewery + Recipe Foundation.

## Repository location

Git source of truth (greenfield root):

```text
\\NazarioNAS\USB_3TB\BrewingOS
```

Mapped locally as `B:\BrewingOS`. Runtime data belongs on NAS **internal** paths under `/volume1/Apps/.../brewingos`, not on the USB git root and not under CODEX/investing shares.

## Principles

- Completely separate from investing, AEGIS, and CODEX workloads
- PostgreSQL is the authoritative operational database
- NAS-mounted persistent storage; containers are replaceable
- Private Tailscale access now; identity-aware external access later (ADR-001)
- Recipe versions support immutability once locked / referenced
- Inventory movements use a transaction ledger
- Brewing calculations are deterministic (never AI-authoritative)

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Vite |
| Backend | FastAPI + SQLAlchemy (async) |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Runtime | Docker Compose project `brewingos` |

## Quick start (NAS)

See [docs/NAS_DEPLOYMENT.md](docs/NAS_DEPLOYMENT.md). Reserved ports:

| Service | Port |
|---------|------|
| Frontend | 18181 |
| API | 18182 |
| OpenAPI | http://127.0.0.1:18182/docs |
| Liveness | http://127.0.0.1:18182/health |

## Docs

- [NAS deployment](docs/NAS_DEPLOYMENT.md)
- [NAS persistence](docs/NAS_PERSISTENCE.md)
- [Backup & restore](docs/BACKUP_RESTORE.md)
- [Security (Epic 1)](docs/SECURITY_EPIC1.md)
- [ADR-001 access model](docs/ADR-001-access-model.md)
- [ADR-002 orientation decisions](docs/ADR-002-epic1-orientation-decisions.md)
- [ADR-003 calculation formulas v1](docs/ADR-003-calculation-formulas-v1.md)
- [Isolation execution status](docs/ISOLATION_EXECUTION_STATUS.md)
- [Increment 1](docs/INCREMENT_1.md)
- [Increment 2](docs/INCREMENT_2.md)
- [Increment 3](docs/INCREMENT_3.md)
- [Increment 4](docs/INCREMENT_4.md)
- [Increment 5](docs/INCREMENT_5.md)
- [Increment 6](docs/INCREMENT_6.md)
- [Increment 7](docs/INCREMENT_7.md)
- [Epic 1 Implementation Review Package](docs/EPIC_1_IMPLEMENTATION_REVIEW.md)
- [Codex Epic 1 Formal Handoff Report](docs/CODEX_EPIC1_HANDOFF_REPORT.md)

## Epic 1 scope

Brewery setup, equipment, ingredient library, inventory ledger, recipes + versions,
deterministic predictions, ready-to-brew checks. Brew Day execution starts in Epic 2.

## License

Private — personal use.
