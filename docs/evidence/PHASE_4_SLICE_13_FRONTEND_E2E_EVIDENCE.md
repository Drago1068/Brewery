# Phase 4 Slice 13 Evidence — FRONTEND_E2E

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `a6777d440a580e97405cf1e4db7153fb303f164a` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_12_DELTA_REVIEW.md` |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `FRONTEND_E2E` |
| Ancestry from `v0.4.0-phase4-spec` | PASS |

## Exact normative extraction

| ID | SPEC_SECTION | NORMATIVE_RULE | DEPENDENCIES | CURRENT_IMPLEMENTATION (pre) | MISSING_BEHAVIOR | UI_SURFACE | API_DEPENDENCY | READ_MODEL_DEPENDENCY | ACCESSIBILITY_REQUIREMENT | E2E_REQUIREMENT | TEST_SURFACE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P4-FR-082 | §38–39 / §44 | Keyboard + 360 px workflows for measurement, reminder ack, state review, note capture | happy-path backend through Close | none | worksheet UI + a11y | `/ferment/[id]` | GET/POST fermentation APIs | session serialize | labels, focus, errors associated, landmarks | Playwright keyboard/360 | `phase4.spec.ts`, `assertFermentA11y` |
| P4-AC-045 | §45 | Worksheet keyboard/360 measurement/reminder/state/note; operable; errors associated | FR-082 | none | same | worksheet | measurements, reminders | status/stages/reminders | Playwright + a11y inspection | yes | `P4-AC-045` test |
| P4-AC-050 | §45 | Playwright ACTIVE→complete fermentation→conditioning→assess→handoff; states/IDs §9/§14 | FR-015,019,020,041 (backend already) | none | UI-driven happy path | lifecycle commands | complete/skip/assess/handoff | status + assessment/handoff ids | n/a beyond operable controls | yes | `P4-AC-050` test |

Notes for §38 “record action / media / waive”: ACTIONS and JOURNAL clusters remain unauthorized for this slice. Note capture is satisfied via measurement `note` on the authoritative RecordMeasurement contract. Waive/complete lifecycle surfaces already exist on backend; worksheet exposes complete/skip/assess/handoff and readiness state.

## Frontend authority boundary

Frontend renders and submits against backend contracts only. No client-side lifecycle, calculation, readiness, handoff, or yeast authority. Derived gravity/readiness/handoff displayed from GET read model.

`FRONTEND_AUTHORITY_VIOLATION=NO`  
`SLICE_13_AI_AUTHORITY_VIOLATION=NO`

## APIs / read models reused

| Surface | Reuse |
|---|---|
| `GET /fermentation-sessions/{id}` | Full worksheet state |
| `POST …/measurements` | Gravity / conditioning temp + note |
| `POST …/reminders/{id}/acknowledge` | Reminder ack ≠ satisfaction |
| `POST …/commands/complete-fermentation` | Lifecycle |
| `POST …/commands/skip-conditioning` | Conditioning path (default plan) |
| `POST …/commands/assess-packaging-readiness` | Readiness (R3 override when OG UNKNOWN) |
| `POST …/commands/record-packaging-readiness-handoff` | Handoff |
| `POST …/commands/pause|resume|abort|close` | Session commands |
| Brew entry `POST …/brew-sessions/{id}/start` | Start then navigate |

### Compatibility change

`GET /fermentation-sessions` (ListSessions, §30) added as owner summary index for dashboard resume and brew→ferment navigation after conflict. No domain mutation behavior.

`EXISTING_API_REUSED=YES`  
`READ_MODEL_COMPATIBILITY_CHANGE=YES` (ListSessions only)

## UI implementation

| Path | Role |
|---|---|
| `apps/web/lib/fermentation.ts` | Types + non-authoritative command builders |
| `apps/web/app/ferment/[id]/page.tsx` | Worksheet: status, stages, measurements+note, reminders, lifecycle, readiness/handoff |
| `apps/web/app/brew/[id]/page.tsx` | Start/resume fermentation entry when brew COMPLETED |
| `apps/web/app/page.tsx` | Active fermentation resume banner |
| `apps/web/app/layout.tsx` | Nav + Phase 4 footer |
| `apps/web/app/globals.css` | Ferment status/toolbar styles |

## Action / error / empty / concurrency

- Mutations refresh revision then POST (`fermentationCommand` / `measurementCommand`)
- 409 → alert + authoritative refresh
- `#ferment-session-error` `role="alert"` focused
- Forms `aria-describedby` when error present
- Loading: polite live region; not-found empty with link home
- `data-busy` on worksheet for E2E idle

`FRONTEND_ACTION_CONTRACT=PASS`  
`FRONTEND_ERROR_STATE_CONTRACT=PASS`  
`FRONTEND_CONCURRENCY_HANDLING=PASS` (API pause then stale complete denial visible)

## Readiness / handoff visibility

Assessment outcome/id and handoff status/version/id rendered from read model. Explicit copy: no packaging execution.

`READINESS_HANDOFF_FRONTEND=PASS`

## Accessibility / responsive

360 px Playwright + keyboard focus on gravity/note/ack; landmarks for stages/reminders/status; timers use `role="timer"` when present; errors associated.

`SLICE_13_ACCESSIBILITY=PASS`  
`RESPONSIVE_FRONTEND=PASS`

## Playwright E2E

| Test | Contract |
|---|---|
| `P4-AC-050 canonical UI happy path…` | ACTIVE→complete→skip conditioning→assess→handoff IDs |
| `P4-AC-045 / P4-FR-082 keyboard and 360px…` | measurement/reminder/state/note |
| `P4-FR-082 stale revision and backend denial…` | denial + focused alert |
| `P4 security: foreign fermentation id…` | 404 nondisclosure |

Helpers: `seedActiveFermentation`, `assertFermentA11y`, `clickAndWaitFerment`, `waitForFermentIdle`.

`PLAYWRIGHT_ACCEPTANCE=PASS` (`.playwright-p4s13.txt`: 12 passed, 1 skipped performance)

## Exact FR/AC proofs

| ID | Spec | Frontend | Backend/read model | Automated test | E2E | Evidence |
|---|---|---|---|---|---|---|
| P4-FR-082 | §38–39 | `/ferment/[id]` | GET + mutations | `lib/fermentation.test.ts` | AC-045/security/stale | this artifact |
| P4-AC-045 | §45 | worksheet a11y | measurements/reminders | Playwright AC-045 | yes | this artifact |
| P4-AC-050 | §45 | lifecycle buttons | complete/skip/assess/handoff | Playwright AC-050 | yes | this artifact |

`P4_FR_082=PASS`  
`P4_AC_045=PASS`  
`P4_AC_050=PASS`

## Security

- Foreign UUID → not found UI; GET 404 for foreign owner (`test_list_sessions_hides_foreign_owner`)
- Backend denials surface as alerts; buttons are not authorization
- No Phase 5 packaging controls

`SECURITY_ACCEPTANCE=PASS`

## Serialization / Phase 5 / AI

| Gate | Result |
|---|---|
| SLICE_11_SERIALIZATION_REGRESSION | PASS (`test_slice11_serialization_regression_idempotent_close_payload`) |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |
| SLICE_13_AI_AUTHORITY_VIOLATION | NO |

## Predecessor regressions

| Suite | Result |
|---|---|
| Full API pytest (SQLite) | PASS (`.pytest-p4s13-reg.txt`, exit 0) |
| Vitest | PASS (after relative import fix) |
| ESLint | PASS |
| Playwright full suite | PASS (12 passed / 1 skipped) |
| Phase 3 late-evidence tz compare | Fixed `_aware(utc_now())` in `brew_day.py` (SQLite monkeypatch naive clock) |

Includes Phase 1A/2/3 and Phase 4 slice suites collected by full pytest.

## Incidental backend note

ListSessions + brew_day aware-clock coercion are subordinate compatibility/regression fixes; no ACTIONS/JOURNAL/Phase 5 behavior.

## Traceability

`SLICE_13_FR_IMPLEMENTED=1/1`  
`SLICE_13_AC_VERIFIED=2/2`  
`SLICE_13_ADV_VERIFIED=0/0`  
`TRACEABILITY=PASS`

## Self-review

Falsified: client authority, packaging UI, silent 409 success, foreign id disclosure, override without gravity leaf, brew-idle helper trapping ferment busy state, R3 NOT_READY without override, measurement note missing at 360 px. Repaired seed gravity leaf, `clickAndWaitFerment`/`data-busy`, assess R3 override for UNKNOWN OG.

`IMPLEMENTATION_SELF_REVIEW=PASS`
