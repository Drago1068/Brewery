# ADR-001 — BrewingOS Access Model

**Status:** Accepted  
**Date:** 2026-08-08  
**Context:** BrewingOS must run on NazarioNAS beside investing/AEGIS/CODEX without shared blast radius.

## Decision

1. **Now (Epic 1–2):** Private Tailscale-only access.
   - Expose BrewingOS via Tailscale Serve/Service named for BrewingOS only.
   - No Tailscale Funnel for BrewingOS.
   - No router port-forwards / UPnP for BrewingOS.
   - PostgreSQL never published on the host.

2. **Later (gated):** Identity-aware external access via Cloudflare Tunnel (outbound-only) + Cloudflare Access MFA in front of the BrewingOS edge service.

## Non-goals

- Sharing auth, networks, databases, or Tailscale Serve routes with investing, AEGIS, CODEX, or `docker/claude`.
- Public Basic-auth Funnel gateways.

## Consequences

- Home LAN and approved tailnet devices can reach BrewingOS after Serve is configured.
- External users cannot reach BrewingOS until the Cloudflare Access gate is explicitly enabled and the security checklist passes.
- Host ports `18181`/`18182` (or the next free `1818x` pair) are reserved for BrewingOS bring-up only; they must not displace other apps.
