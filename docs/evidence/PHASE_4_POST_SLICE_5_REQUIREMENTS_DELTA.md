# Phase 4 Post–Slice 5 Requirements Delta

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Audit input commit (authoritative Slice 5 anchor) | `b464f97c3e5c886091f12215c21e4e97cc46e995` |
| Branch HEAD at audit | `f87860919d98d97dffe25b9791df0c0759b365a5` (timezone coerce follow-up; no new Phase 4 features) |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Inventory | FR 89 / AC 68 / ADV 42 |
| Audit type | Planning only — no application/migration changes |

## Method

- Normative source: `docs/specifications/PHASE_4_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md` §§44–46.
- Reconciled against Slice 2–5 evidence, Slice 1 commit `17bf72a` + `test_phase4_entry.py` (no Slice 1 evidence markdown), and code under `application/phase4/`, migrations `0004`–`0007`, and `apps/web`/Playwright.
- Status meanings: **IMPLEMENTED** / **VERIFIED** = code + objective tests for the requirement; **PARTIAL** = material code or partial proof with named gap; **NOT_IMPLEMENTED** / **NOT_VERIFIED** = missing feature or missing objective proof.
- `P4-FR-018`: Slice 3 PARTIAL (journal-only) → Slice 4 closed child-row effects → **IMPLEMENTED**.

## Implemented capability map (post Slice 5)

| Domain | Status |
|---|---|
| Fermentation session/stage foundation | IMPLEMENTED (OG UNKNOWN/reconcile gaps) |
| Measurements / corrections / late-entry (measurement) | IMPLEMENTED |
| Derived gravity / stable gravity / attenuation / pitch-rate | IMPLEMENTED (ABV app exposure PARTIAL) |
| Lifecycle SM (pause/resume/abort/complete fermentation) | IMPLEMENTED for those commands |
| Completion assessment / confirmation / invalidation (non-CLOSED) | IMPLEMENTED |
| Durable timers / reminders / child effects | IMPLEMENTED |
| Fermentation→conditioning handoff + conditioning lifecycle/completion | IMPLEMENTED |
| Packaging readiness / close / CLOSED requalify | NOT_IMPLEMENTED |
| Yeast §11 lot/reuse/history/cycles | NOT_IMPLEMENTED |
| Actions / post-pitch additions | NOT_IMPLEMENTED |
| Deviations / waivers | NOT_IMPLEMENTED |
| Journal merge export / notes / media | NOT_IMPLEMENTED |
| Equipment snapshot | PARTIAL (plan snapshot; AC-049 proof missing) |
| Frontend / Playwright Phase 4 | NOT_IMPLEMENTED |
| PostgreSQL concurrency / recovery / security (implemented surfaces) | IMPLEMENTED / PARTIAL |

## Totals

| Class | Count |
|---|---|
| FR IMPLEMENTED | 46/89 |
| FR PARTIAL | 18 |
| FR NOT_IMPLEMENTED | 25 |
| AC VERIFIED | 35/68 |
| AC PARTIAL | 9 |
| AC NOT_VERIFIED | 24 |
| ADV VERIFIED | 24/42 |
| ADV PARTIAL | 5 |
| ADV NOT_VERIFIED | 13 |
| TOTAL_FR_ACCOUNTED | 89/89 |
| TOTAL_AC_ACCOUNTED | 68/68 |
| TOTAL_ADV_ACCOUNTED | 42/42 |

## Master matrix — Functional requirements (89)

| ID | SPEC_SECTION | SHORT_TITLE | DEPENDENCIES | STATUS | PRIMARY_IMPLEMENTATION | PRIMARY_TEST | EVIDENCE | SLICE | BLOCKING_DEP | NOTES |
|---|---|---|---|---|---|---|---|---|---|---|
| P4-FR-001 | §44/Session and handoff | Start a fermentation session only from an owned `COMPLETED` brew sess… | AC:004 ADV:022 | IMPLEMENTED | commands.py / test_phase4_entry.py | PHASE_4 entry tests / commit 17bf72a | slice/evidence | 1 | — | — |
| P4-FR-002 | §44/Session and handoff | Immutable-reference `pitched_at`, yeast-addition note, and nullable `… | AC:004 ADV:022 | IMPLEMENTED | commands.py yeast pitch reference | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-003 | §44/Session and handoff | Pin OG consumption from the current pre-pitch `ORIGINAL_GRAVITY` leaf… | AC:004,010 ADV:021,020 | IMPLEMENTED | og_consumption.py | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-004 | §44/Session and handoff | When OG is absent, store `og_availability=UNKNOWN` and still allow st… | AC:004 ADV:021 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-005 | §44/Session and handoff | Provide `ReconcileUpstreamOriginalGravity` to pin a later Phase 3 OG … | AC:010 ADV:020 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-006 | §44/Session and handoff | Reject start when the pitch handoff is missing on an owned completed … | AC:005 ADV:— | IMPLEMENTED | commands.py | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-007 | §44/Session and handoff | Return `404` nondisclosure when the brew session is missing or not ow… | AC:006 ADV:003 | IMPLEMENTED | sessions.py ownership | test_phase4_entry.py / security | slice/evidence | 1 | — | — |
| P4-FR-008 | §44/Session and handoff | Enforce at most one non-aborted fermentation session per brew session… | AC:007 ADV:023 | PARTIAL | unique constraint; CLOSED path unreacha… | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-009 | §44/Session and handoff | Allow a new start after `ABORTED` that reuses the same accepted pitch… | AC:008 ADV:— | IMPLEMENTED | commands.py restart after abort | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-010 | §44/Session and handoff | Allow multiple concurrent fermentation sessions for one user only whe… | AC:009 ADV:— | IMPLEMENTED | commands.py | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-011 | §44/Session and handoff | Materialize `phase4-plan-v1` atomically in the start transaction with… | AC:004,027,028,049,064 ADV:029,039 | PARTIAL | plan.py; equipment snapshot / schedule … | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-012 | §44/Session and handoff | Never mutate `RecipeVersion`, `BrewSession`, Phase 3 measurements, pi… | AC:001,010 ADV:020 | IMPLEMENTED | Phase 4 ops do not mutate Phase 3 entit… | slice evidence | slice/evidence | 1-5 | — | — |
| P4-FR-013 | §44/Session and handoff | Record packaging readiness facts without creating packaging sessions … | AC:011 ADV:017 | NOT_IMPLEMENTED | PackagingReadinessHandoff model only | — | slice/evidence | — | — | — |
| P4-FR-014 | §44/Session and handoff | Scope start idempotency to `brew_session_id` before a fermentation se… | AC:004 ADV:001 | IMPLEMENTED | operations.py brew-scoped start key | test_phase4_entry.py | slice/evidence | 1 | — | — |
| P4-FR-015 | §44/Lifecycle | Implement §9.4 as the sole session command transition contract; §9.5 … | AC:012,050,057,058 ADV:024,033 | PARTIAL | lifecycle.py allowlist; packaging/close… | SLICE_3/5 | slice/evidence | 3-5 | — | — |
| P4-FR-016 | §44/Lifecycle | Reject invalid transitions with `409 INVALID_TRANSITION` and no parti… | AC:012,068 ADV:012,024,033,042 | IMPLEMENTED | fail-closed transitions for implemented… | lifecycle/conditioning tests | slice/evidence | 3-5 | — | — |
| P4-FR-017 | §44/Lifecycle | Persist `pause_origin_state` and resume only to that origin. | AC:013 ADV:024 | IMPLEMENTED | transitions.py pause_origin | test_phase4_lifecycle.py | slice/evidence | 3 | — | — |
| P4-FR-018 | §44/Lifecycle | Apply Phase 3-equivalent timer/reminder child effects on pause, resum… | AC:013,016,029,057 ADV:011,034 | IMPLEMENTED | child_effects.py; closed by Slice 4 (+5… | PHASE_4_SLICE_4 + SLICE_5 | slice/evidence | 4 | — | — |
| P4-FR-019 | §44/Lifecycle | Separate fermentation completion from conditioning start. | AC:023,050 ADV:— | IMPLEMENTED | completion vs StartConditioning | SLICE_3/5 | slice/evidence | 3/5 | — | — |
| P4-FR-020 | §44/Lifecycle | Keep conditioning completion distinct from fermentation completion. | AC:050,053 ADV:— | IMPLEMENTED | distinct conditioning assessment | SLICE_5 | slice/evidence | 5 | — | — |
| P4-FR-021 | §44/Lifecycle | Abort with reason 10–1000 characters, preserved history, and §9.6 chi… | AC:016,057 ADV:012,034 | IMPLEMENTED | transitions.abort + child effects | SLICE_3/4 | slice/evidence | 3 | — | — |
| P4-FR-022 | §44/Lifecycle | Close only when a current `READY` or `READY_WITH_WAIVERS` handoff exi… | AC:017 ADV:012 | NOT_IMPLEMENTED | CloseFermentationSession missing | — | slice/evidence | — | — | — |
| P4-FR-023 | §44/Lifecycle | On `SkipConditioning`, move `FERMENTATION_COMPLETE` → `CONDITIONING_C… | AC:014 ADV:— | IMPLEMENTED | SkipConditioning | SLICE_5 | slice/evidence | 5 | — | — |
| P4-FR-024 | §44/Lifecycle | Deny a second `ACTIVE_FERMENTATION` or `CONDITIONING` row (`409 STAGE… | AC:012,060 ADV:036 | IMPLEMENTED | stage reuse §9.8 | SLICE_5 AC-060 | slice/evidence | 5 | — | — |
| P4-FR-025 | §44/Measurements and time | Enforce `FERMENTATION_GRAVITY` schema, bounds, method/context, and re… | AC:020 ADV:004,025 | IMPLEMENTED | measurements.py | SLICE_2 | slice/evidence | 2 | — | — |
| P4-FR-026 | §44/Measurements and time | Enforce `FERMENTATION_TEMPERATURE` schema and `-5..40` degC inclusive. | AC:020 ADV:026 | IMPLEMENTED | measurements.py | SLICE_2 matrix | slice/evidence | 2 | — | — |
| P4-FR-027 | §44/Measurements and time | Enforce `FERMENTATION_PH` schema and `2.5..8.0` inclusive. | AC:020 ADV:— | IMPLEMENTED | measurements.py | SLICE_2 matrix | slice/evidence | 2 | — | — |
| P4-FR-028 | §44/Measurements and time | Enforce `CONDITIONING_TEMPERATURE` with required CONDITIONING `stage_… | AC:020 ADV:— | IMPLEMENTED | CONDITIONING_TEMPERATURE | SLICE_2/5 | slice/evidence | 2/5 | — | — |
| P4-FR-029 | §44/Measurements and time | Persist `observed_at` and server `recorded_at` separately in UTC per … | AC:020,063 ADV:019,038 | IMPLEMENTED | time_validation.py | SLICE_2 | slice/evidence | 2 | — | — |
| P4-FR-030 | §44/Measurements and time | Reject naive, missing-offset, and >5-minute-future timestamps with `4… | AC:020 ADV:026 | IMPLEMENTED | time_validation.py | SLICE_2 | slice/evidence | 2 | — | — |
| P4-FR-031 | §44/Measurements and time | Append measurement corrections without overwrite, unique current leaf… | AC:020,024 ADV:006 | IMPLEMENTED | corrections | SLICE_2 | slice/evidence | 2 | — | — |
| P4-FR-032 | §44/Measurements and time | Reject cross-session measurement linkage. | AC:020 ADV:004 | IMPLEMENTED | FK + security | SLICE_2 security | slice/evidence | 2 | — | — |
| P4-FR-033 | §44/Calculations | Compute apparent attenuation via the accepted function as a ratio; ex… | AC:021 ADV:— | IMPLEMENTED | try_apparent_attenuation_ratio | SLICE_2 domain | slice/evidence | 2 | — | — |
| P4-FR-034 | §44/Calculations | Compute fermentation progress with the zero-denominator and clipping … | AC:021 ADV:— | IMPLEMENTED | fermentation_progress | SLICE_2 domain | slice/evidence | 2 | — | — |
| P4-FR-035 | §44/Calculations | Evaluate stable gravity exclusively with `phase4-stable-gravity-v1`. | AC:018,019 ADV:005,025 | IMPLEMENTED | stable_gravity_evaluator | SLICE_2 | slice/evidence | 2 | — | — |
| P4-FR-036 | §44/Calculations | Compute ABV with accepted `(OG-FG)×131.25` when defined. | AC:021 ADV:— | PARTIAL | calc in packages/calculations; not expo… | domain unit only | slice/evidence | 2 | — | — |
| P4-FR-037 | §44/Calculations | Label pitch-rate outputs `CALCULATED` and omit them when volume/OG/ra… | AC:021 ADV:— | IMPLEMENTED | pitch_rate.py + read_models | test_phase4_pitch_rate.py | slice/evidence | 2 | — | — |
| P4-FR-038 | §44/Calculations | Convert Plato to SG only through `phase4-plato-to-sg-v1`, rejecting o… | AC:019,062 ADV:037 | IMPLEMENTED | plato_to_sg | SLICE_2 / AC-062 coverage | slice/evidence | 2 | — | — |
| P4-FR-039 | §44/Completion and conditioning | Do not mark fermentation complete from elapsed time alone. | AC:055,022 ADV:007 | IMPLEMENTED | completion.py | SLICE_3 | slice/evidence | 3 | — | — |
| P4-FR-040 | §44/Completion and conditioning | Evaluate fermentation eligibility with §14.2 and persist unsuccessful… | AC:022,053 ADV:007,032 | IMPLEMENTED | completion.py | SLICE_3 | slice/evidence | 3 | — | — |
| P4-FR-041 | §44/Completion and conditioning | Move to `FERMENTATION_COMPLETE` only on successful `CompleteFermentat… | AC:023 ADV:002 | IMPLEMENTED | CompleteFermentation | SLICE_3 | slice/evidence | 3 | — | — |
| P4-FR-042 | §44/Completion and conditioning | Apply override limits in §14.5. | AC:022,059 ADV:032,035 | IMPLEMENTED | override limits | SLICE_3 | slice/evidence | 3 | — | — |
| P4-FR-043 | §44/Completion and conditioning | Invalidate and destinate state per §14.6 with no implicit reopen afte… | AC:024,025,047,061 ADV:006 | PARTIAL | §14.6 for non-CLOSED paths; CLOSED/hand… | SLICE_3/5 | slice/evidence | 3-5 | — | — |
| P4-FR-044 | §44/Completion and conditioning | Version packaging handoffs with exactly one current row and preserve … | AC:026,061 ADV:017 | NOT_IMPLEMENTED | handoff versioning commands missing | — | slice/evidence | — | — | — |
| P4-FR-045 | §44/Completion and conditioning | Evaluate conditioning with §14.3. | AC:053 ADV:— | IMPLEMENTED | conditioning eligibility | SLICE_5 | slice/evidence | 5 | — | — |
| P4-FR-046 | §44/Completion and conditioning | Freeze conditioning mode in the start snapshot; deny mode selection a… | AC:027 ADV:— | IMPLEMENTED | mode frozen in snapshot | SLICE_5 | slice/evidence | 5 | — | — |
| P4-FR-047 | §44/Completion and conditioning | Allow skip of conditioning only when the snapshot declares `condition… | AC:014,015 ADV:— | IMPLEMENTED | skip guards | SLICE_5 | slice/evidence | 5 | — | — |
| P4-FR-048 | §44/Timers and reminders | Persist timers in PostgreSQL with Phase 3-equivalent lifecycle. | AC:029 ADV:010 | IMPLEMENTED | timers.py | SLICE_4 | slice/evidence | 4 | — | — |
| P4-FR-049 | §44/Timers and reminders | Recover timers/reminders after refresh, API restart, Redis loss, and … | AC:029 ADV:009,010 | IMPLEMENTED | PostgreSQL authority | SLICE_4 recovery | slice/evidence | 4 | — | — |
| P4-FR-050 | §44/Timers and reminders | Treat reminder acknowledgement as distinct from requirement satisfact… | AC:030,051 ADV:— | IMPLEMENTED | ACK≠SATISFIED | SLICE_4 | slice/evidence | 4 | — | — |
| P4-FR-051 | §44/Timers and reminders | Emit at most one expiry event when a deadline passes during outage. | AC:029 ADV:011 | IMPLEMENTED | single expiry | SLICE_4 | slice/evidence | 4 | — | — |
| P4-FR-052 | §44/Additions and actions | Materialize `FERMENTATION`/`DRY_HOP` additions with §21.2 timing (`FR… | AC:031 ADV:— | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-053 | §44/Additions and actions | Allow exactly one planned occurrence per source and deny runtime repe… | AC:032 ADV:— | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-054 | §44/Additions and actions | Allow normal unplanned addition execution only while `ACTIVE` or `CON… | AC:012,068 ADV:031,042 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-055 | §44/Additions and actions | Record addition corrections with Phase 3 leaf semantics adapted to th… | AC:024 ADV:006 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-056 | §44/Additions and actions | Record actions using the closed §21.1 enum. | AC:056 ADV:— | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-057 | §44/Additions and actions | Keep addition execution at zero inventory-ledger effect. | AC:033 ADV:— | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-058 | §44/Deviations, waivers, late entry | Record derived deviations with §22 identity and supersession. | AC:020 ADV:006 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-059 | §44/Deviations, waivers, late entry | Support waivers with reason/actor/timestamp/effect for the §10.3 waiv… | AC:051,059 ADV:008,035 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-060 | §44/Deviations, waivers, late entry | Reject non-waivable waiver requests with `409 WAIVER_PROHIBITED`. | AC:054 ADV:008 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-061 | §44/Deviations, waivers, late entry | Enforce late-entry windows in §24 and the sole §31 `phase4-terminal-a… | AC:047,048,068 ADV:012,042 | PARTIAL | measurement late-entry windows; termina… | SLICE_2 | slice/evidence | 2 | — | — |
| P4-FR-062 | §44/Journal, media, export | Merge Phase 4 journal events with Phase 3 using `(occurred_at, record… | AC:046 ADV:019 | NOT_IMPLEMENTED | append-only journal exists; merge expor… | — | slice/evidence | — | — | — |
| P4-FR-063 | §44/Journal, media, export | Emit the closed event vocabulary in §26. | AC:046 ADV:019 | PARTIAL | subset of §26 vocabulary for implemente… | journal writers | slice/evidence | 1-5 | — | — |
| P4-FR-064 | §44/Journal, media, export | Support notes/media under Phase 3 media security architecture. | AC:047,052 ADV:013 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-065 | §44/Journal, media, export | Export JSON and human-readable summaries including original and curre… | AC:046 ADV:019 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-066 | §44/Yeast and inventory | Allow optional same-owner yeast lot linkage with an immutable metadat… | AC:034,035 ADV:027 | NOT_IMPLEMENTED | pitch reference only; no lot snapshot l… | — | slice/evidence | — | — | — |
| P4-FR-067 | §44/Yeast and inventory | Enforce yeast source-pair agreement, ownership, temporal, and aborted… | AC:034 ADV:018,027 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-068 | §44/Yeast and inventory | Provide pitch history by session, lot, and user from snapshots. | AC:035 ADV:— | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-069 | §44/Yeast and inventory | Reject circular lineage under transactional locking. | AC:034 ADV:018 | NOT_IMPLEMENTED | — | — | slice/evidence | — | — | — |
| P4-FR-070 | §44/Yeast and inventory | Must not post automatic inventory consumption. | AC:033 ADV:017 | PARTIAL | no Phase 4 ledger posts today; AC-033 p… | vacuous hold | slice/evidence | 1-5 | — | — |
| P4-FR-071 | §44/API, idempotency, concurrency, security | Require `operation_id` on all Phase 4 mutation commands. | AC:037 ADV:001 | PARTIAL | required on implemented mutations; not … | operations.py | slice/evidence | 1-5 | — | — |
| P4-FR-072 | §44/API, idempotency, concurrency, security | Implement `phase4-operation-v1` including tombstones, rollback, clien… | AC:037,066,068 ADV:001,030,041,042 | PARTIAL | phase4-operation-v1 present; terminal-a… | operations.py | slice/evidence | 1-5 | — | — |
| P4-FR-073 | §44/API, idempotency, concurrency, security | Enforce optimistic revision conflicts as `409 STALE_REVISION`. | AC:036,065 ADV:002,024,040 | IMPLEMENTED | STALE_REVISION on implemented OCC paths | slice concurrency | slice/evidence | 1-5 | — | — |
| P4-FR-074 | §44/API, idempotency, concurrency, security | Serialize completion and lifecycle transitions, including Close, agai… | AC:036,065,068 ADV:002,028,040,042 | PARTIAL | OCC/lock for implemented completions; C… | closure tests | slice/evidence | 3-5 | — | — |
| P4-FR-075 | §44/API, idempotency, concurrency, security | Enforce owner-only access (`404` cross-owner) including nested source… | AC:006,038 ADV:003,015,027 | PARTIAL | IDOR on implemented surfaces; yeast nes… | security suites | slice/evidence | 1-5 | — | — |
| P4-FR-076 | §44/API, idempotency, concurrency, security | Preserve CSRF protections on every new mutating route. | AC:039 ADV:014 | PARTIAL | CSRF middleware applies to new routes; … | shared CSRF | slice/evidence | 1-5 | — | — |
| P4-FR-077 | §44/API, idempotency, concurrency, security | Validate units/domains server-side with closed command schemas; unkno… | AC:020,067 ADV:026 | PARTIAL | closed schemas on implemented commands | mass-assignment tests | slice/evidence | 1-5 | — | — |
| P4-FR-078 | §44/Recovery, backup, performance, accessibility, safety | Survive API restart without losing authoritative fermentation state. | AC:029 ADV:010 | IMPLEMENTED | durable GET after restart | SLICE_4/5 recovery | slice/evidence | 4-5 | — | — |
| P4-FR-079 | §44/Recovery, backup, performance, accessibility, safety | Treat Redis as non-authoritative. | AC:029 ADV:009 | IMPLEMENTED | Redis non-authoritative | SLICE_4 | slice/evidence | 4 | — | — |
| P4-FR-080 | §44/Recovery, backup, performance, accessibility, safety | Survive isolated backup/restore of fixture vectors in §35 including m… | AC:040 ADV:030 | NOT_IMPLEMENTED | Phase 4 backup vectors missing | — | slice/evidence | — | — | — |
| P4-FR-081 | §44/Recovery, backup, performance, accessibility, safety | Provide the isolated performance harness in §37 without mutating auth… | AC:041 ADV:016 | NOT_IMPLEMENTED | Phase 4 perf harness missing | — | slice/evidence | — | — | — |
| P4-FR-082 | §44/Recovery, backup, performance, accessibility, safety | Support keyboard and 360 px workflows in §38–39. | AC:045,050 ADV:— | NOT_IMPLEMENTED | no Phase 4 UI | — | slice/evidence | — | — | — |
| P4-FR-083 | §44/Recovery, backup, performance, accessibility, safety | Fail closed on impossible timestamps and hard measurement bounds per … | AC:020 ADV:026 | IMPLEMENTED | fail-closed bounds/time | SLICE_2 | slice/evidence | 2 | — | — |
| P4-FR-084 | §44/Regression and scope | Preserve accepted Phase 3 brew-day behavior and evidence unchanged. | AC:001,042 ADV:020 | PARTIAL | predecessor regressions run per-slice; … | slice reg runs | slice/evidence | — | — | — |
| P4-FR-085 | §44/Regression and scope | Preserve accepted Phase 2 core/calculation/inventory and Phase 1A bro… | AC:043 ADV:— | PARTIAL | 1A/2 suites exist; final Phase 4 candid… | phase1a/2 specs | slice/evidence | — | — | — |
| P4-FR-086 | §44/Regression and scope | Enforce the Phase 5+ leakage matrix in §51. | AC:002,003,011 ADV:017 | PARTIAL | no packaging ops implemented; final lea… | code absence | slice/evidence | 1-5 | — | — |
| P4-FR-087 | §44/Regression and scope | Apply additive migrations from accepted Phase 3 head to verified Phas… | AC:044 ADV:— | PARTIAL | migrations 0004-0007 + test_phase4_migr… | test_phase4_migration.py | slice/evidence | 1-4 | — | — |
| P4-FR-088 | §44/Regression and scope | Reactivate an invalidated stage by reusing `stage_instance_id`, incre… | AC:060,063 ADV:036,038 | IMPLEMENTED | reactivation reuse | SLICE_4/5 | slice/evidence | 4-5 | — | — |
| P4-FR-089 | §44/Regression and scope | After `CLOSED`, evaluate packaging readiness from current evidence wi… | AC:026,059,061 ADV:035 | NOT_IMPLEMENTED | CLOSED requalify missing | — | slice/evidence | — | — | — |

## Master matrix — Acceptance criteria (68)

| ID | SPEC_SECTION | SHORT_TITLE | STATUS | PRIMARY_TEST_LAYER | RECOMMENDED_SLICE | NOTES |
|---|---|---|---|---|---|---|
| P4-AC-001 | §45 | PRECONDITION: git diff from `v0.3.0-phase3`. ACTION: inventory paths. EXPECTED:… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-002 | §45 | PRECONDITION: candidate tree. ACTION: architecture inspection plus executable a… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-003 | §45 | PRECONDITION: implementation. ACTION: map every new table/route/page to a P4-FR… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-004 | §45 | PRECONDITION: owned completed brew with handoff and OG leaf. ACTION: start. EXP… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-005 | §45 | PRECONDITION: owned completed brew, no handoff. ACTION: start. EXPECTED: `422 P… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-006 | §45 | PRECONDITION: foreign brew ID. ACTION: start or GET. EXPECTED: `404`. EVIDENCE:… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-007 | §45 | PRECONDITION: existing CLOSED session. ACTION: second start different key. EXPE… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-008 | §45 | PRECONDITION: ABORTED session. ACTION: new start different key. EXPECTED: new A… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-009 | §45 | PRECONDITION: two completed brews. ACTION: two starts. EXPECTED: two ACTIVE ses… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-010 | §45 | PRECONDITION: Phase 3 OG corrected after pin. ACTION: read session; then reconc… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-011 | §45 | PRECONDITION: ready path. ACTION: record handoff and scan packaging tables. EXP… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-012 | §45 | PRECONDITION: each invalid edge in §9.4. ACTION: command. EXPECTED: 409, no wri… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-013 | §45 | PRECONDITION: CONDITIONING then pause. ACTION: resume. EXPECTED: CONDITIONING, … | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-014 | §45 | PRECONDITION: `conditioning_required=false` and FERMENTATION_COMPLETE. ACTION: … | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-015 | §45 | PRECONDITION: `conditioning_required=true`. ACTION: skip. EXPECTED: 409. EVIDEN… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-016 | §45 | PRECONDITION: abort from ACTIVE with running timers. ACTION: abort. EXPECTED: §… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-017 | §45 | PRECONDITION: NOT_READY current handoff. ACTION: close. EXPECTED: 409 HANDOFF_N… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-018 | §45 | PRECONDITION: §15 golden vectors. ACTION: evaluator. EXPECTED: exact table outc… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-019 | §45 | PRECONDITION: Plato near spread boundary. ACTION: convert+evaluate. EXPECTED: a… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-020 | §45 | PRECONDITION: measurement fixtures. ACTION: submit bounds/method/stage/time cas… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-021 | §45 | PRECONDITION: OG/FG pairs including undefined. ACTION: attenuation/progress/ABV… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-022 | §45 | PRECONDITION: F1–F4 fail. ACTION: CompleteFermentation. EXPECTED: 422, persiste… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-023 | §45 | PRECONDITION: eligible ACTIVE. ACTION: complete. EXPECTED: FERMENTATION_COMPLET… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-024 | §45 | PRECONDITION: confirmed then gravity correction. ACTION: correct. EXPECTED: §14… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-025 | §45 | PRECONDITION: CLOSED with READY handoff. ACTION: completion-affecting correctio… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-026 | §45 | PRECONDITION: CLOSED with current READY handoff; FG correction within 24h inval… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-027 | §45 | PRECONDITION: sparse recipe. ACTION: start then complete fermentation. EXPECTED… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-028 | §45 | PRECONDITION: duplicate FERMENTATION_FOUNDATION. ACTION: start. EXPECTED: 422, … | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-029 | §45 | PRECONDITION: timers on F-REC-1. ACTION: refresh, API restart, Redis stop, dead… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-030 | §45 | PRECONDITION: required gravity reminder. ACTION: acknowledge. EXPECTED: still u… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-031 | §45 | PRECONDITION: DRY_HOP timing_minutes=2880. ACTION: start. EXPECTED: due_at = pi… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-032 | §45 | PRECONDITION: planned addition. ACTION: runtime repeat command. EXPECTED: 409. … | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-033 | §45 | PRECONDITION: addition execute/retry. ACTION: ledger query. EXPECTED: zero cons… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-034 | §45 | PRECONDITION: mismatched yeast source pair / aborted source / cycle race. ACTIO… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-035 | §45 | PRECONDITION: live lot metadata change after start. ACTION: GET history. EXPECT… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-036 | §45 | PRECONDITION: each §32 race. ACTION: PostgreSQL interleaving. EXPECTED: stated … | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-037 | §45 | PRECONDITION: every mutation family. ACTION: missing operation_id; same key dif… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-038 | §45 | PRECONDITION: two owners. ACTION: nested IDOR matrix §33. EXPECTED: 404 no muta… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-039 | §45 | PRECONDITION: browser mutation. ACTION: missing CSRF / bad Origin. EXPECTED: 40… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-040 | §45 | PRECONDITION: F-REC-1/2 backup. ACTION: isolated restore. EXPECTED: §35 equalit… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-041 | §45 | PRECONDITION: harness dataset. ACTION: §37 operations. EXPECTED: thresholds; ze… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-042 | §45 | PRECONDITION: accepted Phase 3 suites. ACTION: run canonical E2E + PostgreSQL s… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-043 | §45 | PRECONDITION: Phase 2/1A suites. ACTION: run core/calculation/inventory and pha… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-044 | §45 | PRECONDITION: fresh DB and upgraded Phase 3 DB. ACTION: migrate to Phase 4 head… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-045 | §45 | PRECONDITION: worksheet. ACTION: keyboard and 360px measurement/reminder/state/… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-046 | §45 | PRECONDITION: mixed Phase 3 journal + backdated Phase 4 correction same occurre… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-047 | §45 | PRECONDITION: CLOSED. ACTION: each DENY cell in §25. EXPECTED: 409, no mutation… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-048 | §45 | PRECONDITION: ABORTED. ACTION: new measurement. EXPECTED: 409 TERMINAL_SESSION_… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-049 | §45 | PRECONDITION: equipment profile edit after start. ACTION: GET session. EXPECTED… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-050 | §45 | PRECONDITION: canonical happy path. ACTION: Playwright ACTIVE→complete fermenta… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-051 | §45 | PRECONDITION: waiver vs later gravity. ACTION: race and supersession. EXPECTED:… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-052 | §45 | PRECONDITION: malformed media. ACTION: upload. EXPECTED: Phase 3 MIME/decoder r… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-053 | §45 | PRECONDITION: duration elapsed, temperature missed, conditioning required both.… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-054 | §45 | PRECONDITION: any nonterminal fermentation session. ACTION: waive `pitched_at`,… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-055 | §45 | PRECONDITION: planned fermentation duration elapsed, fewer than three valid gra… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-056 | §45 | PRECONDITION: ACTIVE session. ACTION: RecordAction with a type not in §21.1. EX… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-057 | §45 | PRECONDITION: PAUSED from CONDITIONING; separately CONDITIONING_COMPLETE. ACTIO… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-058 | §45 | PRECONDITION: HANDOFF_READY then completion-affecting gravity making F1 fail. A… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-059 | §45 | PRECONDITION: R1 and R2 true, OG UNKNOWN. ACTION: (a) assess without waiver; (b… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-060 | §45 | PRECONDITION: CONDITIONING started then fermentation-affecting correction. ACTI… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-061 | §45 | PRECONDITION: CLOSED READY then FG correction within 24h. ACTION: AssessPackagi… | NOT_VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-062 | §45 | PRECONDITION: FERMENTATION_GRAVITY raw Plato 100; just-outside PLATO_MAX; just-… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-063 | §45 | PRECONDITION: conditioning completed 10 days ago; session still nonterminal; co… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-064 | §45 | PRECONDITION: abort then restart same brew/recipe with `details.schedule`. ACTI… | PARTIAL | per matrix | see remaining inventory | — |
| P4-AC-065 | §45 | PRECONDITION: two clients, `expected_revision=10`. ACTION: CompleteFermentation… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-066 | §45 | PRECONDITION: CompleteFermentation commits; HTTP lost; new gravity commits; cli… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-067 | §45 | PRECONDITION: any mutation. ACTION: extra undocumented JSON field (including ow… | VERIFIED | per matrix | see remaining inventory | — |
| P4-AC-068 | §45 | PRECONDITION: CLOSED at T; valid planned and unplanned additions occurred at T−… | NOT_VERIFIED | per matrix | see remaining inventory | — |

## Master matrix — Adversarial scenarios (42)

| ID | SPEC_SECTION | SHORT_TITLE | STATUS | RECOMMENDED_SLICE | NOTES |
|---|---|---|---|---|---|
| P4-ADV-001 | §46 | PRECONDITION: recorded measurement. ACTION: same operation_id same payload; the… | VERIFIED | see remaining inventory | — |
| P4-ADV-002 | §46 | PRECONDITION: eligible session. ACTION: two concurrent CompleteFermentation. EX… | VERIFIED | see remaining inventory | — |
| P4-ADV-003 | §46 | PRECONDITION: owner A session. ACTION: owner B GET/mutate nested IDs. EXPECTED:… | VERIFIED | see remaining inventory | — |
| P4-ADV-004 | §46 | PRECONDITION: session A. ACTION: attach measurement to session B via API and di… | VERIFIED | see remaining inventory | — |
| P4-ADV-005 | §46 | PRECONDITION: three stable readings then newer 1.020. ACTION: evaluate / comple… | VERIFIED | see remaining inventory | — |
| P4-ADV-006 | §46 | PRECONDITION: confirmed complete. ACTION: invalidating vs note-only correction.… | VERIFIED | see remaining inventory | — |
| P4-ADV-007 | §46 | PRECONDITION: two gravities only. ACTION: complete. EXPECTED: 422, persisted IN… | VERIFIED | see remaining inventory | — |
| P4-ADV-008 | §46 | PRECONDITION: any state. ACTION: waive pitched_at or yeast note. EXPECTED: 409 … | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-009 | §46 | PRECONDITION: F-REC-1. ACTION: stop Redis. EXPECTED: GET authority unchanged; c… | VERIFIED | see remaining inventory | — |
| P4-ADV-010 | §46 | PRECONDITION: F-REC-1. ACTION: API restart. EXPECTED: same IDs. EVIDENCE: GET. … | VERIFIED | see remaining inventory | — |
| P4-ADV-011 | §46 | PRECONDITION: deadline during outage. ACTION: refresh. EXPECTED: one expiry eve… | VERIFIED | see remaining inventory | — |
| P4-ADV-012 | §46 | PRECONDITION: CLOSED and ABORTED. ACTION: full §25 DENY set. EXPECTED: 409. EVI… | PARTIAL | see remaining inventory | — |
| P4-ADV-013 | §46 | PRECONDITION: upload. ACTION: polyglot/MIME mismatch. EXPECTED: 415/422. EVIDEN… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-014 | §46 | PRECONDITION: mutation. ACTION: wrong CSRF. EXPECTED: 403. EVIDENCE: API. RELAT… | PARTIAL | see remaining inventory | — |
| P4-ADV-015 | §46 | PRECONDITION: GET. ACTION: hostile session ID. EXPECTED: 404/422, no 500 leak. … | VERIFIED | see remaining inventory | — |
| P4-ADV-016 | §46 | PRECONDITION: perf harness. ACTION: run §37. EXPECTED: no authoritative user wr… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-017 | §46 | PRECONDITION: Phase 4 API. ACTION: create packaging session. EXPECTED: fail clo… | PARTIAL | see remaining inventory | — |
| P4-ADV-018 | §46 | PRECONDITION: two sessions. ACTION: circular and concurrent opposite yeast edge… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-019 | §46 | PRECONDITION: mixed journal. ACTION: backdated correction same occurred_at as P… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-020 | §46 | PRECONDITION: Phase 4 client. ACTION: mutate pitch handoff. EXPECTED: no Phase … | VERIFIED | see remaining inventory | — |
| P4-ADV-021 | §46 | PRECONDITION: waived OG brew, first ferment gravity 3 days later. ACTION: start… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-022 | §46 | PRECONDITION: valid handoff null pitch_temperature_c. ACTION: start. EXPECTED: … | VERIFIED | see remaining inventory | — |
| P4-ADV-023 | §46 | PRECONDITION: CLOSED session. ACTION: start different key. EXPECTED: 409 EXISTS… | PARTIAL | see remaining inventory | — |
| P4-ADV-024 | §46 | PRECONDITION: PAUSED from ACTIVE, stale complete. ACTION: complete. EXPECTED: 4… | VERIFIED | see remaining inventory | — |
| P4-ADV-025 | §46 | PRECONDITION: 1.014/1.012/1.010 spaced 24h. ACTION: stable eval. EXPECTED: NOT_… | VERIFIED | see remaining inventory | — |
| P4-ADV-026 | §46 | PRECONDITION: future observed_at >5 min or naive TZ. ACTION: measure. EXPECTED:… | VERIFIED | see remaining inventory | — |
| P4-ADV-027 | §46 | PRECONDITION: yeast lot of user B cited by user A. ACTION: enrich. EXPECTED: 40… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-028 | §46 | PRECONDITION: completion read then gravity insert. ACTION: interleave without w… | VERIFIED | see remaining inventory | — |
| P4-ADV-029 | §46 | PRECONDITION: live equipment edit. ACTION: historical GET. EXPECTED: unchanged … | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-030 | §46 | PRECONDITION: restore. ACTION: replay old start key. EXPECTED: replay, no secon… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-031 | §46 | PRECONDITION: unplanned addition while PAUSED. ACTION: create. EXPECTED: 409/42… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-032 | §46 | PRECONDITION: override with zero gravities. ACTION: complete override. EXPECTED… | VERIFIED | see remaining inventory | — |
| P4-ADV-033 | §46 | PRECONDITION: HANDOFF_READY. ACTION: abort. EXPECTED: 409 INVALID_TRANSITION. E… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-034 | §46 | PRECONDITION: PAUSED origin CONDITIONING. ACTION: abort. EXPECTED: ABORTED, §9.… | VERIFIED | see remaining inventory | — |
| P4-ADV-035 | §46 | PRECONDITION: UNKNOWN OG, R1/R2 true. ACTION: record READY without waiver; then… | NOT_VERIFIED | see remaining inventory | — |
| P4-ADV-036 | §46 | PRECONDITION: INVALIDATED CONDITIONING row. ACTION: StartConditioning creating … | VERIFIED | see remaining inventory | — |
| P4-ADV-037 | §46 | PRECONDITION: ACTIVE. ACTION: 100 Plato gravity. EXPECTED: `422 PLATO_OUT_OF_DO… | VERIFIED | see remaining inventory | — |
| P4-ADV-038 | §46 | PRECONDITION: day-10 reactivation. ACTION: new temperature. EXPECTED: accepted … | VERIFIED | see remaining inventory | — |
| P4-ADV-039 | §46 | PRECONDITION: `details.schedule` present. ACTION: start. EXPECTED: schedule in … | PARTIAL | see remaining inventory | — |
| P4-ADV-040 | §46 | PRECONDITION: shared expected_revision. ACTION: complete vs measure. EXPECTED: … | VERIFIED | see remaining inventory | — |
| P4-ADV-041 | §46 | PRECONDITION: lost assessment response then new gravity. ACTION: retry same key… | VERIFIED | see remaining inventory | — |
| P4-ADV-042 | §46 | PRECONDITION: an unplanned historical addition is accepted at `closed_at+24h`; … | NOT_VERIFIED | see remaining inventory | — |

## Remaining FR inventory (PARTIAL + NOT_IMPLEMENTED)

| FR_ID | SPEC_SECTION | TITLE | DEPENDENCIES | WHY_NOT_COMPLETE | RECOMMENDED_SLICE | BLOCKING |
|---|---|---|---|---|---|---|
| P4-FR-004 | §44/Session and handoff | When OG is absent, store `og_availability=UNKNOWN` and… | see matrix | OG UNKNOWN start path absent (start currently requires OG) | ENTRY_OG_RECONCILE | NO |
| P4-FR-005 | §44/Session and handoff | Provide `ReconcileUpstreamOriginalGravity` to pin a la… | see matrix | ReconcileUpstreamOriginalGravity missing | ENTRY_OG_RECONCILE | NO |
| P4-FR-008 | §44/Session and handoff | Enforce at most one non-aborted fermentation session p… | see matrix | CLOSED unreachable; post-CLOSED uniqueness not exercised | PACKAGING_READINESS_CLOSE | YES |
| P4-FR-011 | §44/Session and handoff | Materialize `phase4-plan-v1` atomically in the start t… | see matrix | Equipment snapshot / schedule hash edges (AC-049/064) incomplete | PLAN_EQUIPMENT_CLOSURE | NO |
| P4-FR-013 | §44/Session and handoff | Record packaging readiness facts without creating pack… | see matrix | Packaging readiness facts/commands not implemented | PACKAGING_READINESS_CLOSE | YES |
| P4-FR-015 | §44/Lifecycle | Implement §9.4 as the sole session command transition … | see matrix | §9.4 packaging assess/record/close transitions missing | PACKAGING_READINESS_CLOSE | YES |
| P4-FR-022 | §44/Lifecycle | Close only when a current `READY` or `READY_WITH_WAIVE… | see matrix | CloseFermentationSession not implemented | PACKAGING_READINESS_CLOSE | YES |
| P4-FR-036 | §44/Calculations | Compute ABV with accepted `(OG-FG)×131.25` when define… | see matrix | ABV calculator exists; Phase 4 session exposure missing | CALC_READ_MODEL_CLOSURE | NO |
| P4-FR-043 | §44/Completion and conditioning | Invalidate and destinate state per §14.6 with no impli… | see matrix | CLOSED invalidation destinations unimplemented | PACKAGING_READINESS_CLOSE | YES |
| P4-FR-044 | §44/Completion and conditioning | Version packaging handoffs with exactly one current ro… | see matrix | Versioned packaging handoffs unimplemented | PACKAGING_READINESS_CLOSE | YES |
| P4-FR-052 | §44/Additions and actions | Materialize `FERMENTATION`/`DRY_HOP` additions with §2… | see matrix | Addition materialization missing | ACTIONS_ADDITIONS | NO |
| P4-FR-053 | §44/Additions and actions | Allow exactly one planned occurrence per source and de… | see matrix | Planned occurrence uniqueness missing | ACTIONS_ADDITIONS | NO |
| P4-FR-054 | §44/Additions and actions | Allow normal unplanned addition execution only while `… | see matrix | Unplanned/terminal addition policy missing | ACTIONS_ADDITIONS | NO |
| P4-FR-055 | §44/Additions and actions | Record addition corrections with Phase 3 leaf semantic… | see matrix | Addition corrections missing | ACTIONS_ADDITIONS | NO |
| P4-FR-056 | §44/Additions and actions | Record actions using the closed §21.1 enum. | see matrix | RecordAction enum missing | ACTIONS_ADDITIONS | NO |
| P4-FR-057 | §44/Additions and actions | Keep addition execution at zero inventory-ledger effec… | see matrix | Zero-ledger addition proof path missing | ACTIONS_ADDITIONS | NO |
| P4-FR-058 | §44/Deviations, waivers, late entry | Record derived deviations with §22 identity and supers… | see matrix | Derived deviations missing | DEVIATIONS | NO |
| P4-FR-059 | §44/Deviations, waivers, late entry | Support waivers with reason/actor/timestamp/effect for… | see matrix | Fermentation waivers missing | WAIVERS_READINESS | YES |
| P4-FR-060 | §44/Deviations, waivers, late entry | Reject non-waivable waiver requests with `409 WAIVER_P… | see matrix | WAIVER_PROHIBITED path missing | WAIVERS_READINESS | NO |
| P4-FR-061 | §44/Deviations, waivers, late entry | Enforce late-entry windows in §24 and the sole §31 `ph… | see matrix | Terminal-addition §31.1 policy missing | ACTIONS_ADDITIONS | YES |
| P4-FR-062 | §44/Journal, media, export | Merge Phase 4 journal events with Phase 3 using `(occu… | see matrix | Journal merge export missing | JOURNAL_MEDIA_EXPORT | NO |
| P4-FR-063 | §44/Journal, media, export | Emit the closed event vocabulary in §26. | see matrix | Full §26 vocabulary not emitted | JOURNAL_MEDIA_EXPORT | NO |
| P4-FR-064 | §44/Journal, media, export | Support notes/media under Phase 3 media security archi… | see matrix | Notes/media missing | JOURNAL_MEDIA_EXPORT | NO |
| P4-FR-065 | §44/Journal, media, export | Export JSON and human-readable summaries including ori… | see matrix | JSON/HTML export missing | JOURNAL_MEDIA_EXPORT | NO |
| P4-FR-066 | §44/Yeast and inventory | Allow optional same-owner yeast lot linkage with an im… | see matrix | Yeast lot linkage + immutable snapshot missing | YEAST_PROVENANCE | NO |
| P4-FR-067 | §44/Yeast and inventory | Enforce yeast source-pair agreement, ownership, tempor… | see matrix | Source-pair / ownership / temporal rules missing | YEAST_PROVENANCE | NO |
| P4-FR-068 | §44/Yeast and inventory | Provide pitch history by session, lot, and user from s… | see matrix | Pitch history queries missing | YEAST_PROVENANCE | NO |
| P4-FR-069 | §44/Yeast and inventory | Reject circular lineage under transactional locking. | see matrix | Circular lineage lock missing | YEAST_PROVENANCE | NO |
| P4-FR-070 | §44/Yeast and inventory | Must not post automatic inventory consumption. | see matrix | Vacuous today; needs addition/readiness proof | ACTIONS_ADDITIONS | NO |
| P4-FR-071 | §44/API, idempotency, concurrency, security | Require `operation_id` on all Phase 4 mutation command… | see matrix | Must cover all future mutation families | CROSS_CUTTING_EACH_SLICE | NO |
| P4-FR-072 | §44/API, idempotency, concurrency, security | Implement `phase4-operation-v1` including tombstones, … | see matrix | Terminal-addition tombstone paths incomplete | ACTIONS_ADDITIONS | NO |
| P4-FR-074 | §44/API, idempotency, concurrency, security | Serialize completion and lifecycle transitions, includ… | see matrix | Close vs evidence races not implemented | PACKAGING_READINESS_CLOSE | YES |
| P4-FR-075 | §44/API, idempotency, concurrency, security | Enforce owner-only access (`404` cross-owner) includin… | see matrix | Nested yeast source IDOR pending yeast slice | YEAST_PROVENANCE | NO |
| P4-FR-076 | §44/API, idempotency, concurrency, security | Preserve CSRF protections on every new mutating route. | see matrix | Dedicated Phase 4 CSRF matrix incomplete | FINAL_ACCEPTANCE | NO |
| P4-FR-077 | §44/API, idempotency, concurrency, security | Validate units/domains server-side with closed command… | see matrix | Must extend to new command schemas | CROSS_CUTTING_EACH_SLICE | NO |
| P4-FR-080 | §44/Recovery, backup, performance, accessibility, safety | Survive isolated backup/restore of fixture vectors in … | see matrix | Phase 4 backup/restore vectors missing | FINAL_ACCEPTANCE | NO |
| P4-FR-081 | §44/Recovery, backup, performance, accessibility, safety | Provide the isolated performance harness in §37 withou… | see matrix | Phase 4 performance harness missing | FINAL_ACCEPTANCE | NO |
| P4-FR-082 | §44/Recovery, backup, performance, accessibility, safety | Support keyboard and 360 px workflows in §38–39. | see matrix | No Phase 4 UI / a11y Playwright | FRONTEND_E2E | NO |
| P4-FR-084 | §44/Regression and scope | Preserve accepted Phase 3 brew-day behavior and eviden… | see matrix | Final candidate regression proof pending | FINAL_ACCEPTANCE | NO |
| P4-FR-085 | §44/Regression and scope | Preserve accepted Phase 2 core/calculation/inventory a… | see matrix | Final 1A/2 regression proof pending | FINAL_ACCEPTANCE | NO |
| P4-FR-086 | §44/Regression and scope | Enforce the Phase 5+ leakage matrix in §51. | see matrix | Final leakage scan acceptance pending | FINAL_ACCEPTANCE | NO |
| P4-FR-087 | §44/Regression and scope | Apply additive migrations from accepted Phase 3 head t… | see matrix | Final migration round-trip acceptance pending | FINAL_ACCEPTANCE | NO |
| P4-FR-089 | §44/Regression and scope | After `CLOSED`, evaluate packaging readiness from curr… | see matrix | CLOSED requalify missing | PACKAGING_READINESS_CLOSE | YES |

## Remaining AC inventory (PARTIAL + NOT_VERIFIED)

| AC_ID | VALIDATES | STATUS | MISSING_PROOF | TEST_LAYER | RECOMMENDED_SLICE |
|---|---|---|---|---|---|
| P4-AC-001 | see title | PARTIAL | objective proof for remaining FR | per §47 | FINAL_ACCEPTANCE |
| P4-AC-002 | see title | PARTIAL | objective proof for remaining FR | per §47 | FINAL_ACCEPTANCE |
| P4-AC-003 | see title | PARTIAL | objective proof for remaining FR | per §47 | FINAL_ACCEPTANCE |
| P4-AC-007 | see title | PARTIAL | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-010 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | ENTRY_OG_RECONCILE |
| P4-AC-011 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-017 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-025 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-026 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-028 | see title | PARTIAL | objective proof for remaining FR | per §47 | PLAN_EQUIPMENT_CLOSURE |
| P4-AC-031 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | ACTIONS_ADDITIONS |
| P4-AC-032 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | ACTIONS_ADDITIONS |
| P4-AC-033 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | ACTIONS_ADDITIONS |
| P4-AC-034 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | YEAST_PROVENANCE |
| P4-AC-035 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | YEAST_PROVENANCE |
| P4-AC-039 | see title | PARTIAL | objective proof for remaining FR | per §47 | FINAL_ACCEPTANCE |
| P4-AC-040 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | FINAL_ACCEPTANCE |
| P4-AC-041 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | FINAL_ACCEPTANCE |
| P4-AC-045 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | FRONTEND_E2E |
| P4-AC-046 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | JOURNAL_MEDIA_EXPORT |
| P4-AC-047 | see title | PARTIAL | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-048 | see title | PARTIAL | objective proof for remaining FR | per §47 | ACTIONS_ADDITIONS |
| P4-AC-049 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | PLAN_EQUIPMENT_CLOSURE |
| P4-AC-050 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | FRONTEND_E2E |
| P4-AC-051 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | WAIVERS_READINESS |
| P4-AC-052 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | JOURNAL_MEDIA_EXPORT |
| P4-AC-054 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | WAIVERS_READINESS |
| P4-AC-056 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | ACTIONS_ADDITIONS |
| P4-AC-058 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-059 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | WAIVERS_READINESS |
| P4-AC-061 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | PACKAGING_READINESS_CLOSE |
| P4-AC-064 | see title | PARTIAL | objective proof for remaining FR | per §47 | PLAN_EQUIPMENT_CLOSURE |
| P4-AC-068 | see title | NOT_VERIFIED | objective proof for remaining FR | per §47 | ACTIONS_ADDITIONS |

## Remaining ADV inventory (PARTIAL + NOT_VERIFIED)

| ADV_ID | TARGET | STATUS | MISSING_PROOF | TEST_LAYER | RECOMMENDED_SLICE |
|---|---|---|---|---|---|
| P4-ADV-008 | PRECONDITION: any state. ACTION: waive pitched_at… | NOT_VERIFIED | adversarial exercise | per §47 | WAIVERS_READINESS |
| P4-ADV-012 | PRECONDITION: CLOSED and ABORTED. ACTION: full §2… | PARTIAL | adversarial exercise | per §47 | PACKAGING_READINESS_CLOSE |
| P4-ADV-013 | PRECONDITION: upload. ACTION: polyglot/MIME misma… | NOT_VERIFIED | adversarial exercise | per §47 | JOURNAL_MEDIA_EXPORT |
| P4-ADV-014 | PRECONDITION: mutation. ACTION: wrong CSRF. EXPEC… | PARTIAL | adversarial exercise | per §47 | FINAL_ACCEPTANCE |
| P4-ADV-016 | PRECONDITION: perf harness. ACTION: run §37. EXPE… | NOT_VERIFIED | adversarial exercise | per §47 | FINAL_ACCEPTANCE |
| P4-ADV-017 | PRECONDITION: Phase 4 API. ACTION: create packagi… | PARTIAL | adversarial exercise | per §47 | FINAL_ACCEPTANCE |
| P4-ADV-018 | PRECONDITION: two sessions. ACTION: circular and … | NOT_VERIFIED | adversarial exercise | per §47 | YEAST_PROVENANCE |
| P4-ADV-019 | PRECONDITION: mixed journal. ACTION: backdated co… | NOT_VERIFIED | adversarial exercise | per §47 | JOURNAL_MEDIA_EXPORT |
| P4-ADV-021 | PRECONDITION: waived OG brew, first ferment gravi… | NOT_VERIFIED | adversarial exercise | per §47 | ENTRY_OG_RECONCILE |
| P4-ADV-023 | PRECONDITION: CLOSED session. ACTION: start diffe… | PARTIAL | adversarial exercise | per §47 | PACKAGING_READINESS_CLOSE |
| P4-ADV-027 | PRECONDITION: yeast lot of user B cited by user A… | NOT_VERIFIED | adversarial exercise | per §47 | YEAST_PROVENANCE |
| P4-ADV-029 | PRECONDITION: live equipment edit. ACTION: histor… | NOT_VERIFIED | adversarial exercise | per §47 | PLAN_EQUIPMENT_CLOSURE |
| P4-ADV-030 | PRECONDITION: restore. ACTION: replay old start k… | NOT_VERIFIED | adversarial exercise | per §47 | FINAL_ACCEPTANCE |
| P4-ADV-031 | PRECONDITION: unplanned addition while PAUSED. AC… | NOT_VERIFIED | adversarial exercise | per §47 | ACTIONS_ADDITIONS |
| P4-ADV-033 | PRECONDITION: HANDOFF_READY. ACTION: abort. EXPEC… | NOT_VERIFIED | adversarial exercise | per §47 | PACKAGING_READINESS_CLOSE |
| P4-ADV-035 | PRECONDITION: UNKNOWN OG, R1/R2 true. ACTION: rec… | NOT_VERIFIED | adversarial exercise | per §47 | WAIVERS_READINESS |
| P4-ADV-039 | PRECONDITION: `details.schedule` present. ACTION:… | PARTIAL | adversarial exercise | per §47 | PLAN_EQUIPMENT_CLOSURE |
| P4-ADV-042 | PRECONDITION: an unplanned historical addition is… | NOT_VERIFIED | adversarial exercise | per §47 | ACTIONS_ADDITIONS |

## Cross-cutting requirement review

| Theme | Classification | Notes |
|---|---|---|
| Access control / CSRF / closed schemas | B — satisfied for implemented slices; needs extension per new surface | FR-071–077 PARTIAL |
| Audit / journal vocabulary | C — write path exists; merge/export incomplete | FR-062–065 |
| Accessibility / responsive UX | C — no Phase 4 UI | FR-082, AC-045 |
| Frontend | C — dedicated UI/E2E slice required | PHASE_4_FRONTEND_REMAINING=YES |
| Recovery (restart/Redis) | A/B — proven for timers/conditioning surfaces | FR-078/079 IMPLEMENTED |
| Media / equipment / provenance | C — media/equipment gaps remain | FR-064, AC-049, ADV-029 |
| AI boundary | B — docs/architecture forbid LLM authority; executable Phase 4 negative suite still needed | AI_BOUNDARY=PARTIAL |
| Migration guarantees | B — 0004–0007 present; final acceptance round-trip pending | FR-087 PARTIAL |
| Performance | C/D — harness missing; may be final-acceptance-only if no feature code | FR-081 |
| Backup/restore | C/D — Phase 4 vectors missing | FR-080 |
| Concurrency | B — strong for Slices 3–5; Close/addition races remain | FR-074 PARTIAL |
| Deterministic calculations | A/B — core goldens present; ABV exposure PARTIAL | FR-033–038 |

## Frontend / UX gap

`PHASE_4_FRONTEND_REMAINING=YES`

Governing IDs still requiring UI/E2E:
- FR: `P4-FR-082`
- AC: `P4-AC-045`, `P4-AC-050`
- ADV: none uniquely UI-only beyond export/media visuals covered elsewhere

A dedicated **FRONTEND_E2E** slice is required before final Phase 4 candidate; backend completeness ≠ Phase 4 completeness.

## Yeast domain gap

| Metric | Value |
|---|---|
| YEAST_REQUIREMENTS_TOTAL | 19 |
| YEAST_REQUIREMENTS_IMPLEMENTED | 5 (`P4-FR-002`, `P4-FR-033`, `P4-FR-037`, `P4-AC-004` pitch-temp path, `P4-ADV-022`) |
| YEAST_REQUIREMENTS_REMAINING | 14 |

Remaining yeast IDs and dependencies:
- `P4-FR-066` → inventory lot optional linkage; depends on session start (SATISFIED)
- `P4-FR-067` → depends on FR-066 enrichment command
- `P4-FR-068` → depends on FR-066 snapshots
- `P4-FR-069` → depends on FR-067 edges + PG locking
- `P4-FR-070` → proven with additions/readiness (PARTIAL vacuous)
- `P4-AC-021` attenuation/ABV vectors PARTIAL vs FR-036 exposure
- `P4-AC-034`, `P4-AC-035` → FR-066/067/068/069
- `P4-AC-054` → FR-060 waiver prohibitions (yeast note non-waivable)
- `P4-ADV-008`, `P4-ADV-018`, `P4-ADV-021`, `P4-ADV-027` → FR-060/066–069/004

Pitch-rate calc (`P4-FR-037`) does **not** satisfy §11 provenance.

## Media / equipment / provenance gap

Remaining IDs: `P4-FR-064`, `P4-AC-049`, `P4-AC-052`, `P4-ADV-013`, `P4-ADV-029`; journal export `P4-FR-062/065`, `P4-AC-046`, `P4-ADV-019`.

## AI boundary

`AI_BOUNDARY=PARTIAL`

- Spec §41 + architecture: no LLM authority over calculations/lifecycle (PASS by design).
- Remaining: executable negative assertions (`P4-AC-002`) and final candidate scan.
- No accepted Phase 4 AI-assistance feature remains to implement.

## Performance / scale / recovery gap

| Item | Type |
|---|---|
| FR-078/079 recovery | Implementation present; keep in final acceptance re-proof |
| FR-080 backup/restore | FINAL_ACCEPTANCE_EVIDENCE_REQUIRED (+ fixture vectors; may need small harness code) |
| FR-081 performance | FINAL_ACCEPTANCE_EVIDENCE_REQUIRED (isolated harness) |

Do not open a feature slice solely for FR-081 unless harness scaffolding is treated as acceptance tooling.

## Phase 5 leakage

`PHASE_5_PLUS_OPERATIONAL_LEAKAGE=NO` for remaining Phase 4 work: packaging readiness facts and handoffs are Phase 4; packaging execution/inventory consumption remain prohibited (`P4-FR-013/086`).

## Dependency graph (remaining clusters)

```
ENTRY(done) -> YEAST_PROVENANCE
ENTRY(done) -> ENTRY_OG_RECONCILE
ENTRY(done)+PLAN -> ACTIONS_ADDITIONS -> (proves FR-070)
ACTIONS_ADDITIONS -> DEVIATIONS (optional parallel after measurements)
CONDITIONING_COMPLETE(done) -> WAIVERS_READINESS -> PACKAGING_READINESS_CLOSE
PACKAGING_READINESS_CLOSE -> CLOSED paths (FR-008/043/089)
JOURNAL writers(done) -> JOURNAL_MEDIA_EXPORT
Sufficient backend surfaces -> FRONTEND_E2E
All feature clusters -> FINAL_ACCEPTANCE
```

## Candidate remaining clusters

| CLUSTER_NAME | FR_IDS | AC_IDS | ADV_IDS | DEPENDENCIES | COMPLEXITY | CAN_BE_FINAL_IMPL_SLICE |
|---|---|---|---|---|---|---|
| YEAST_PROVENANCE | 066–069 | 034,035 | 018,027 | ENTRY SATISFIED | MEDIUM | NO |
| ENTRY_OG_RECONCILE | 004,005 | 010 | 021 | ENTRY SATISFIED | SMALL | NO |
| ACTIONS_ADDITIONS | 052–057,061,070,072(part) | 031–033,048,056,068 | 031,042 | PLAN+ACTIVE SATISFIED | LARGE | NO |
| DEVIATIONS | 058 | — | — | measurements SATISFIED | SMALL | NO |
| WAIVERS_READINESS | 059,060 | 051,054,059 | 008,035 | conditioning/complete SATISFIED | MEDIUM | NO |
| PACKAGING_READINESS_CLOSE | 013,015(part),022,044,043(part),074(part),008(part),089 | 007,011,017,025,026,047,058,061 | 012,023,033 | WAIVERS + CONDITIONING_COMPLETE | LARGE | NO |
| JOURNAL_MEDIA_EXPORT | 062–065 | 046,052 | 013,019 | journal writers | MEDIUM | NO |
| PLAN_EQUIPMENT_CLOSURE | 011(part) | 028,049,064 | 029,039 | ENTRY | SMALL | NO |
| CALC_READ_MODEL_CLOSURE | 036 | 021(part) | — | calculations | SMALL | NO |
| FRONTEND_E2E | 082 | 045,050 | — | backend surfaces | LARGE | NO |
| FINAL_ACCEPTANCE | 076,080,081,084–087 | 001–003,039–044 | 014,016,017,030 | all features | LARGE | YES (acceptance-only) |

`REMAINING_IMPLEMENTATION_CLUSTER_COUNT=11` (10 feature + final acceptance)

## Recommended next slice

| Field | Value |
|---|---|
| RECOMMENDED_NEXT_SLICE | `YEAST_PROVENANCE_AND_PITCH_HISTORY` |
| NEXT_SLICE_FR_IDS | P4-FR-066, P4-FR-067, P4-FR-068, P4-FR-069 |
| NEXT_SLICE_AC_IDS | P4-AC-034, P4-AC-035 |
| NEXT_SLICE_ADV_IDS | P4-ADV-018, P4-ADV-027 |
| NEXT_SLICE_DEPENDENCIES | SATISFIED (Slice 1 entry + pitch reference) |
| WHY_THIS_SLICE_NEXT | Smallest coherent unimplemented Phase 4 pillar (“Yeast”); dependencies already satisfied; does not mix packaging readiness/close; unlocks nested IDOR/security (FR-075) and history provenance before later inventory-adjacent proofs. |
| NEXT_SLICE_COULD_COMPLETE_PHASE_4_FEATURE_IMPLEMENTATION | NO |
| REMAINING_AFTER_NEXT_SLICE | ENTRY_OG_RECONCILE; ACTIONS_ADDITIONS; DEVIATIONS; WAIVERS_READINESS; PACKAGING_READINESS_CLOSE; JOURNAL_MEDIA_EXPORT; PLAN_EQUIPMENT_CLOSURE; CALC_READ_MODEL_CLOSURE; FRONTEND_E2E; FINAL_ACCEPTANCE |

## Final-acceptance-only work

`FINAL_ACCEPTANCE_ONLY_WORK` (not ordinary feature slices):
- Complete 89/68/42 traceability reconciliation on the final candidate
- PostgreSQL acceptance suite (full §32 matrix)
- Migration round-trip (FR-087 / AC-044)
- Security suite including CSRF matrix (FR-076 / AC-039 / ADV-014)
- Concurrency suite including Close/addition races
- Recovery re-proof F-REC vectors
- Performance harness §37 (FR-081 / AC-041 / ADV-016)
- Accessibility + Playwright Phase 4 + predecessor regressions (FR-082/084/085)
- Backup/restore §35 (FR-080 / AC-040 / ADV-030)
- Final Phase 5 leakage scan (FR-086 / AC-002/003/011)
- Implementation evidence consolidation

## Declarations

- `PHASE_4_IMPLEMENTATION_CANDIDATE=NOT_YET_ASSIGNED`
- `PHASE_4_IMPLEMENTATION_ACCEPTANCE=NOT_YET_GRANTED`
- `PHASE_5_IMPLEMENTATION=NOT_AUTHORIZED`

## Audit integrity

- Spec not modified.
- Application code / migrations not modified by this audit.
- Only this evidence artifact is added for the delta commit.

