# BrewingOS NAS Deployment

Deploy BrewingOS as an isolated Compose project on NazarioNAS. Do not disturb investing, AEGIS, CODEX, or Claude Docker workspaces.

> **Epic 1 posture:** This stack is **development-grade** (Vite-dev frontend, no application login, Tailscale/loopback isolation per ADR-001/002). That is acceptable for private single-user NAS bring-up and is **explicitly not** the long-term production security/deployment architecture. See `docs/SECURITY_EPIC1.md` deferred production track before labeling any environment production.

## Prerequisites

- Docker Compose on NazarioNAS
- Tailscale on NazarioNAS (`signaldesk-nas` or current NAS node)
- Ability to create paths under `/volume1/Apps` and `/volume1/AppBackups`

## Directory layout

Preferred (when UGOS shared folder exists and sudo/admin can create it):

```text
/volume1/Apps/stacks/brewingos/
/volume1/Apps/data/brewingos/...
```

**Current live layout (2026-08-08):** `/volume1/Apps` was not creatable without sudo, so BrewingOS uses the existing writable Docker apps tree (same parent as `aegis-trading-os-v2` / `pos-platform`, separate leaf):

```text
/volume1/docker/brewingos/stack
/volume1/docker/brewingos/data/postgres
/volume1/docker/brewingos/data/storage
/volume1/docker/brewingos/logs
/volume1/docker/brewingos/secrets/.env
/volume1/docker/brewingos/backups
```

## Forbidden paths (never mount or write)

```text
\\NazarioNAS\CODEX\**
\\NazarioNAS\docker\claude\**
\\NazarioNAS\docker\aegis*\**
\\NazarioNAS\docker\pos-platform\**
\\NazarioNAS\personal_folder\deployments\**
```

Git may live on `\\NazarioNAS\USB_3TB\BrewingOS`. Runtime data must not.

## Bring-up

On the NAS host (not Windows Docker Desktop):

```bash
# 1. Create runtime dirs
sudo mkdir -p \
  /volume1/Apps/stacks/brewingos \
  /volume1/Apps/data/brewingos/postgres \
  /volume1/Apps/data/brewingos/storage \
  /volume1/Apps/logs/brewingos \
  /volume1/Apps/secrets/brewingos \
  /volume1/AppBackups/databases/brewingos

# 2. Install secrets
sudo cp .env.example /volume1/Apps/secrets/brewingos/.env
sudo chmod 600 /volume1/Apps/secrets/brewingos/.env
# Edit passwords / secret key before continuing.

# 3. Sync/release compose project into stacks path, then:
cd /volume1/Apps/stacks/brewingos
export COMPOSE_PROJECT_NAME=brewingos
docker compose --env-file /volume1/Apps/secrets/brewingos/.env up -d --build
```

Reserved bring-up ports (if host bind required):

| Service | Port |
|---------|------|
| Frontend | 18181 |
| API | 18182 |

Audit the NAS host first. If either port is taken by another stack, choose the next free `1818x` pair in `.env` — do not stop the other service.

## Tailscale Serve (private)

Do **not** run Serve commands inside `pos-platform-tailscale-1` in a way that replaces:

```text
https://pos-platform.tail86cdea.ts.net → http://ingress:8080
```

Use a dedicated Tailscale Service / node for BrewingOS (`tailscale serve --service=brewingos ...`) once an auth key or admin Service is available.

Until then, use SSH local forwarding from an approved PC:

```powershell
ssh -i $env:USERPROFILE\.ssh\ugreen_nas_ed25519 `
  -L 18181:127.0.0.1:18181 -L 18182:127.0.0.1:18182 `
  Drago1068@192.168.1.12
```

## Non-interference checklist

Before calling deploy done:

- [ ] `docker ps` still shows investing/AEGIS/CODEX-related containers unchanged (if they were running)
- [ ] `\\NazarioNAS\CODEX\SCREENER` untouched
- [ ] `\\NazarioNAS\docker\claude` untouched
- [ ] Networks `brewingos-edge|app|data` contain only BrewingOS endpoints
- [ ] Postgres has no host port published
- [ ] BrewingOS not listening on `8000` or `3000`
- [ ] Backups only under `/volume1/AppBackups/databases/brewingos`
- [ ] Tailscale Serve routes for other apps unchanged

## Local Windows note

Windows Docker Desktop was used only for Increment 1 verification. It must be stopped when working against the NAS stack so host port `8000` cannot collide with AEGIS tooling on the same PC.
