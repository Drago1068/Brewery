# Isolation Plan Execution Status

**Date:** 2026-08-08 (updated after SSH enabled)

## Completed

- ADR-001 + NAS deployment/persistence docs (CODEX deny-list included)
- Compose isolation: project `brewingos`, networks `brewingos-edge|app|data`, ports `18181`/`18182`, loopback bind
- Local Windows `brewingos-*` containers removed
- **NAS deploy live on NazarioNAS** via SSH (`Drago1068` + `ugreen_nas_ed25519`)
- Health/ready/meta OK on `127.0.0.1:18182`
- Sibling check: only added `brewingos-*` containers; **none removed**
- CODEX `SCREENER/config.py` mtime unchanged (`2026-07-18 14:27:28`)
- Networks contain only BrewingOS endpoints

## Live NAS layout (architecture deviation)

`/volume1/Apps` could not be created without sudo. Deployed under the existing writable app pattern:

```text
/volume1/docker/brewingos/stack
/volume1/docker/brewingos/data/postgres
/volume1/docker/brewingos/data/storage
/volume1/docker/brewingos/logs
/volume1/docker/brewingos/secrets/.env   # mode 600
/volume1/docker/brewingos/backups
```

Git remains on USB: `/mnt/@usb/sdb1/BrewingOS` (`\\NazarioNAS\USB_3TB\BrewingOS`).

## Tailscale Serve — deferred (intentionally)

`pos-platform-tailscale-1` already serves:

```text
https://pos-platform.tail86cdea.ts.net (tailnet only)
|-- / proxy http://ingress:8080
```

Per isolation rules, BrewingOS must **not** overwrite that Serve config. Next step is a **dedicated Tailscale Service** (`--service brewingos`) or a BrewingOS-owned Tailscale node/auth key — not a path under POS.

### Temporary private access from your PC

```powershell
ssh -i $env:USERPROFILE\.ssh\ugreen_nas_ed25519 -L 18181:127.0.0.1:18181 -L 18182:127.0.0.1:18182 Drago1068@192.168.1.12
```

Then open `http://127.0.0.1:18181` and API `http://127.0.0.1:18182/health`.

## Forbidden paths still untouched

- `/volume1/CODEX`
- `/volume1/docker/claude`
- `/volume1/docker/aegis-trading-os-v2`
- `/volume1/docker/pos-platform`
- `/volume1/POS-*`
