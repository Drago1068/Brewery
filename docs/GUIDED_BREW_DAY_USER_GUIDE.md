# Guided Brew Day (E2A-6)

Homebrewer-facing Brew-Day Copilot for Epic 2A. Architecture authority remains ADR-004 / ADR-005 / ADR-006.

## Start a Brew Day

1. Open **Recipes**.
2. Open an **ACTIVE** or **LOCKED** recipe version (DRAFT is not eligible).
3. Run **Ready to brew?**
4. GREEN → **Create Brew Plan & Start Brew Day**.
5. YELLOW/RED → explicitly acknowledge findings (they stay YELLOW/RED — never shown as GREEN), then create the plan.
6. The app opens **Brew Day** with a new BrewSession.

## Guided stages

Nine stages: Pre-Brew → Mash-In → Mash → Mash Complete → Boil → Chill/Knockout → Transfer → Yeast Pitch → Brew-Day Audit.

- Advance with **Complete Stage & Continue** (calls the transition API).
- Timers never auto-advance stages.
- Skip requires a reason and warns that remaining REQUIRED measurements on the stage become MISSED.
- No illegal backward transitions are offered.

## Timers

- Start with optional target duration.
- Countdown is visual only; server timestamps are authoritative.
- Refresh/reconnect reconstructs display from persisted timestamps.
- Past-due timers can be explicitly **Observe elapsed**.
- Expiration never advances stages, misses measurements, closes Brew Day, or creates handoff.

## Measurements

- Planned values are labeled **Planned (not measured)**.
- Capture records MEASURED values with confidence.
- Unusual / domain-concern warnings preserve the entered value.
- Input errors are rejected by the API and shown as errors.

## Miss vs waive

- **Missed**: intended but not captured.
- **Waived**: intentionally skipped (reason required).
- Neither creates a measured value (no `0`, no recipe target substitution).

## Corrections / revisions

- Instrument correction keeps original + corrected.
- User revision requires a reason; history remains append-only.

## Offline / sync

Mutating actions generate `client_submission_id` before send. If the network fails, the command is stored in `localStorage` as **UNSYNCED** and replayed on reconnect with the **same** submission ID.

Visible sync states: SYNCED, UNSYNCED, SYNCING, SYNC FAILED, REJECTED, CONFLICT.

OCC conflicts are **not** blindly retried with a new submission ID — refresh server state and reconcile.

## Pause / resume

Pause disables stage advancement. Timers continue on wall-clock time (`ends_at` is not recalculated).

## Close & handoff

- Close is blocked while REQUIRED measurements remain PENDING.
- Close does **not** auto-create fermentation handoff.
- After close, **Continue to Fermentation** creates the explicit handoff → `HANDED_OFF`.
- Abort requires a reason; no handoff; evidence preserved.

## Recovery

Refreshing the browser reloads BrewSession, stages, measurements, timers, and version from the API using the stored session id.
