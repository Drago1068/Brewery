# E2A-6 FINAL REVIEW PACKAGE — Epic 2A

**Increment:** E2A-6 — Guided Brew-Day UI, Offline Resilience & Final Epic 2A Integration  
**Date:** 2026-08-09  
**Governing:** ADR-004, ADR-005, ADR-006

---

## 1. Commit SHA

`ef4876eda62435ec58bdcab90c1dc3c514433101`

## 2. Working-tree status

Clean after E2A-6 commit. No Epic 2B / Epic 3 code.

## 3. Files added/modified

### Frontend added
- `frontend/src/api/*` — shared HTTP + brew-day client
- `frontend/src/offline/*` — durable mutation queue + replay
- `frontend/src/brewDay/*` — Guided Brew-Day panel, stage meta, timer reconstruction
- `frontend/src/lib/ids.ts`
- `frontend/src/e2a6.test.ts`

### Frontend modified
- `App.tsx` / `App.css` — Brew Day nav + copilot styling
- `RecipesPanel.tsx` — Ready-to-Brew → Create Brew Plan & session

### Backend (minimal, documented)
- `GET /api/v1/brew-plans/{id}` — refresh recovery
- Recipe detail greenlet-safe serialization
- Measurement response built before commit / safe datetime attrs (live API durability)

### Docs / scripts
- `docs/GUIDED_BREW_DAY_USER_GUIDE.md`
- `backend/scripts/e2a6_live_journey_persist.py`
- `docs/EPIC_2A_E2A6_FINAL_REVIEW_PACKAGE.md`

## 4. Confirmation no migration 010

Confirmed. No Alembic `010`. Schema remains at `009`.

## 5. UI architecture

View-state SPA (no new router). Brew Day is a first-class view reconstructing from API + `localStorage` session id. Offline queue uses `localStorage` (not React memory). Server remains authoritative.

## 6. Main Guided Brew-Day screen

Header: recipe, batch, session state, sync pill, elapsed time, OCC version.  
Dominant current-stage card + nine-stage rail + measurements + timers + actions.

## 7. Stage progression UX

Explicit **Complete Stage & Continue** → transition API. Skip requires reason + MISSED warning confirmation. No backward transitions offered.

## 8. Measurement UX

Fast capture form with unit/confidence/instrument. Planned labeled separately from MEASURED actuals.

## 9. Warning UX

Unusual/domain-concern banners preserve entered values. Input errors surface as API 422 messages.

## 10. Miss/Waive UX

Distinct controls + copy. Waive requires reason. Neither fabricates values.

## 11. Correction/Revision UX

Instrument correction and reasoned user revision; history retained server-side.

## 12. Timer UX

Visual countdown/count-up from timestamps; Observe elapsed explicit; expiration never advances process.

## 13. Pause/Resume UX

Explicit controls; pause disables advance; wall-clock timer note shown.

## 14. Offline queue architecture

`localStorage` key `brewingos.e2a6.mutationQueue.v1` stores operation, path, payload, `client_submission_id`, expected version, retry/error state.

## 15. Sync state behavior

SYNCED / UNSYNCED / SYNCING / SYNC_FAILED / REJECTED / CONFLICT — visible in header.

## 16. Replay behavior

On `online`, replay keeps original `client_submission_id`. Exact success clears queue item.

## 17. OCC conflict UX

Conflicts mark CONFLICT; no new submission id minting; message prompts reconciliation after refresh.

## 18. Duplicate-submit protection

Idempotent `client_submission_id` + busy guards; queue/replay cannot invent alternate ids for the same action.

## 19. Refresh/restart recovery

Session id persisted; reload fetches session, plan, requirements, timers, report as needed.

## 20. Brew-Day Audit UX

Independent sections; `overall_brew_score` null; no Brew Score UI.

## 21. Close UX

Blocks on REQUIRED PENDING with explanation; success message states handoff is not automatic.

## 22. Abort UX

Strong confirmation + required reason; explains no handoff / no fabrication.

## 23. Fermentation handoff UX

Explicit **Continue to Fermentation** after CLOSED → HANDED_OFF. No FermentationSession.

## 24. Ready-to-Brew integration

ACTIVE/LOCKED only; YELLOW/RED acknowledgement required and not recolored GREEN.

## 25. Responsive/accessibility behavior

Large CTAs, tablet-friendly grids, status text (not color alone), dialog labels, live timer text.

## 26. Frontend tests

`e2a6.test.ts`: stage meta, timer reconstruction, offline queue persistence, OCC conflict id retention, replay with original submission id.  
`npm test` — **10 passed**. `tsc -b` clean.

## 27. Backend test results

```
167 passed, 1 skipped
```

## 28. Epic 1 golden regression

Included in full suite (unchanged formulas).

## 29. E2A-1 through E2A-5 regression

Full suite green; timers still non-authoritative for process; histories append-only.

## 30. Live HTTP/browser E2E results

Live API journey script exercised against Docker backend (`http://127.0.0.1:8000`):
Recipe → activate → readiness/plan → session → start → timer → stage walk → measurement → miss remaining REQUIRED → report → close → handoff → HANDED_OFF.

Browser UI is present and wired; automated browser driver (Playwright) was not added — HTTP journey + unit UI logic tests cover acceptance-critical paths.

## 31. PostgreSQL restart row-persistence results

```
after_restart_status HANDED_OFF
after_restart_events 28
after_restart_obs_history 1
after_restart_timers 1
after_restart_handoffs 1
E2A6_PERSISTENCE_OK
```

Closes E2A-4/E2A-5 row-level persistence limitation.

## 32. Canonical full Brew-Day journey

Documented in `scripts/e2a6_live_journey_persist.py` + Guided Brew Day UI path from Ready-to-Brew.

## 33. Known limitations

- No Playwright browser automation in CI (HTTP journey used instead)
- Offline queue is localStorage (single-browser), not multi-device sync
- BrewAction checklist remains lightweight
- Host `.env` may bind backend to `:8000` rather than compose default `:18182`

## 34. Architecture deviations, if any

Minimal backend fixes only (GET BrewPlan; async ORM serialization safety for recipe/measurement responses). No new aggregates. No migration 010.

## 35. Confirmation no Epic 2B/Epic 3 implementation

Confirmed: no equipment-specific workflow redesign, no FermentationSession, no fermentation diary/targets/packaging/sensory, no Redis/workers/CRDT, no brew score.

## 36. Recommendation: ACCEPT or HOLD Epic 2A

**ACCEPT Epic 2A** — guided UI + offline minimum + live persistence journey verified; regressions green; stop boundary honored.

---

E2A-6 COMPLETE — READY FOR FINAL EPIC 2A REVIEW
