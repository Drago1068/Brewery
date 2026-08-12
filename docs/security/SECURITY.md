# Implemented Security Baseline

- Single-user bootstrap credentials enter through environment variables and are never returned by the API.
- Passwords are stored using the password library's recommended Argon2id hash.
- Login creates a random opaque token; only its secret-salted SHA-256 digest is stored.
- The browser receives an HTTP-only, SameSite=Lax session cookie. `SESSION_COOKIE_SECURE=true` is mandatory behind TLS.
- Every management endpoint authenticates the server session and filters resources by owner.
- PostgreSQL and Redis are isolated on an internal Docker network and have no host ports.
- Web and API bind to `127.0.0.1`; initial development has no public exposure.
- Structured JSON logs avoid request bodies and credentials.
- Audit events cover authenticated workflow mutations.
- `.env` and backup artifacts are ignored by Git.
- npm audit reported zero known dependencies after upgrading patched Vitest and Playwright versions.

## Deployment gates

Before NAS deployment: use TLS through the approved private-access boundary, set secure cookies, rotate all development secrets, restrict filesystem permissions, establish encrypted off-device backups, test restore, run dependency/container scanning, and review log retention. This task makes no NAS configuration change.

