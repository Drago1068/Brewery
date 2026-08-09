# ADR-001 — BrewingOS Access Model

**Status:** Accepted (Epic interim; **not** long-term production security architecture)  
**Date:** 2026-08-08  
**Amended:** 2026-08-09 — clarify interim vs production-grade posture  

**Context:** BrewingOS must run on NazarioNAS beside investing/AEGIS/CODEX without shared blast radius.

## Decision

1. **Now (Epic 1 private single-user NAS stage):** Private Tailscale-only / loopback access.
   - Expose BrewingOS via Tailscale Serve/Service named for BrewingOS only.
   - No Tailscale Funnel for BrewingOS.
   - No router port-forwards / UPnP for BrewingOS.
   - PostgreSQL never published on the host.
   - Application login is **not** required for this stage (see ADR-002 §A). Network isolation is the Epic 1 access control.

2. **Later (gated — required before production / shared / external exposure):** Identity-aware external access via Cloudflare Tunnel (outbound-only) + Cloudflare Access MFA in front of the BrewingOS edge service, **plus** application-level identity (login / IAM) — not network isolation alone.

## Explicit non-promotion rule

ADR-001 network isolation **must not** silently become the permanent production security model by inertia, convenience, or Epic 1 acceptance. Accepting this ADR for Epic 1 means accepting an **interim private-NAS posture**, not approving “no app login forever.”

Promotion to production-grade access requires an explicit PO decision and a follow-on ADR (or ADR-001 revision) covering:

- Application authentication / authorization (beyond `default_actor_id`)
- Identity-aware edge access when any non-tailnet exposure exists
- Confirmation that Cloudflare Access (or equivalent) is configured before public/shared exposure

## Non-goals

- Sharing auth, networks, databases, or Tailscale Serve routes with investing, AEGIS, CODEX, or `docker/claude`.
- Public Basic-auth Funnel gateways.
- Treating Epic 1 “no login + Tailscale” as the finished production architecture.

## Consequences

- Home LAN and approved tailnet devices can reach BrewingOS after Serve is configured.
- External users cannot reach BrewingOS until the Cloudflare Access gate is explicitly enabled and the security checklist passes.
- Host ports `18181`/`18182` (or the next free `1818x` pair) are reserved for BrewingOS bring-up only; they must not displace other apps.
- Epic 1 reviewers may accept this posture **only** as deferred production hardening, not as a closed security architecture.
