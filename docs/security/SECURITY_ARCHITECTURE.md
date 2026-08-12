# Security Architecture

## Baseline Controls
- Authentication required for management interfaces.
- Server-side authorization.
- TLS for remote access.
- Secrets external to source control.
- No secrets in frontend bundles.
- Least-privilege database/application identities.
- Container isolation.
- Dependency scanning.
- Audit logging.
- Backup encryption where supported.
- Restore testing.
- No unnecessary public NAS exposure.

## Data Classification
Public: intentionally published digital menu.
Internal: recipes, inventory, equipment, brew history, learning progress.
Sensitive: credentials, tokens, private configuration, account metadata.

## Digital Menu Boundary
Public menu endpoints expose only explicitly published fields and must not expose inventory costs, internal notes, account data, or operational/admin endpoints.
