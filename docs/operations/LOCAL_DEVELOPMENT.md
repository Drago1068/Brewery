# Local Development

## Boundary

Development uses Docker Compose on the local workstation with repository files on `B:`. No UGREEN NAS service configuration, tunnel, router, or public exposure change is required or authorized.

## Configure

Copy `.env.example` to `.env` and replace every placeholder. `.env` is ignored by Git. Required values are PostgreSQL credentials, bootstrap single-user credentials, and a session secret of at least 32 characters.

Default host-only routes:

- Web: `http://127.0.0.1:18101`
- API: `http://127.0.0.1:18100`
- API readiness: `http://127.0.0.1:18100/health/ready`

PostgreSQL and Redis are not published to the host or public network.

## Commands

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose logs -f api web
docker compose down
```

`docker compose down` preserves the named PostgreSQL volume. `docker compose down -v` deletes development data and must only be used intentionally after a verified backup.

## Workflow

Sign in, create a recipe v1, start its brew session, start Mash, respond to the persisted pH and gravity reminders, record both measurements, complete Mash, and inspect the performance and journal panels. A typical 60-minute Mash makes the gravity reminder due five minutes before the target end. A one-minute test Mash makes both reminders due immediately.

