# Phase 4 Specification Remediation

Remediation date: 2026-08-31 (America/New_York)
Work type: specification only. No Phase 4 application code, tests, migrations, ADRs, tags, merges, NAS access, or implementation authorization.

## Identity

| Item | Value |
|---|---|
| Repository | `//NazarioNAS/USB_3TB/brewing-platform` |
| Branch | `spec/phase4-fermentation-conditioning-yeast` |
| Original reviewed specification commit | `e39a3fbd576c8cafaefad83a9686c5c152c08aec` |
| Original reviewed specification SHA-256 | `B5A80865CFFEAA104828E496C7EF4FCD1D45DE68422B68248D85A7F0E2058DF7` |
| Phase 3 baseline tag | `v0.3.0-phase3` |
| Phase 3 baseline commit | `39c440f234149e67be6dfae948b33393857a153e` |
| `PHASE_3_BASELINE_VERIFIED` | YES (commit is ancestor of HEAD; peeled tag target independently verified in the Codex review as `39c440f`) |
| Independent review artifact | `docs/evidence/PHASE_4_INDEPENDENT_ARCHITECTURE_AND_SPECIFICATION_REVIEW.md` (immutable; not modified) |
| Codex verdict | `PHASE_4_INDEPENDENT_SPECIFICATION_REVIEW=FAIL` |
| `REVIEWED_SPEC_COMMIT` match | YES |
| `SPEC_HASH_VERIFIED` (pre-remediation) | YES |

## Codex verdict (authoritative source: review artifact)

```
PHASE_4_INDEPENDENT_SPECIFICATION_REVIEW=FAIL
P0_FINDINGS=0
P1_FINDINGS=11
BLOCKING_P2_FINDINGS=5
P3_FINDINGS=1
ORPHAN_FR_COUNT=67
ORPHAN_AC_COUNT=26
ORPHAN_ADV_COUNT=20
OPEN_QUESTIONS_ACTUAL=14
OPEN_BLOCKING_QUESTIONS=11
ADR_CANDIDATES_ACTUAL=2
ADR_BLOCKERS=0
PHASE_3_BASELINE_COMPATIBILITY=FAIL
SPECIFICATION_ACCEPTANCE_RECOMMENDED=NO
```

## Finding inventory

| FINDING_ID | SEVERITY | SPEC_REFERENCE | ROOT_CAUSE | REQUIRED_REMEDIATION | AFFECTED_SECTIONS | AFFECTED_FR | AFFECTED_AC | AFFECTED_ADV | ADR_IMPACT | BASELINE_IMPACT | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P4-SPEC-001 | P1 | §6.2; §6.4; §7.1 | OG fallback relabeled post-pitch gravity; no pinned leaf; null pitch temp unspecified | Pin pre-pitch OG leaf; UNKNOWN if absent; explicit reconcile; accept null pitch temperature | 6, 7, 14 | 002–007 | 004–006,010 | 021,022,020 | none | consume Phase 3 OG/handoff correctly | CLOSED |
| P4-SPEC-002 | P1 | §6.1; §9; §17 | Pause origin missing; skip destination U; uniqueness contradictory | Exhaustive §9 tables; pause_origin; skip→CONDITIONING_COMPLETE; unique non-aborted including CLOSED; abort children | 8.4, 9 | 008,009,015–024 | 007,008,012–017 | 023,024,033 | none | none on Phase 3 files | CLOSED |
| P4-SPEC-003 | P1 | §14; §17; §24 | Eligibility/waiver/override/assessment persistence unresolved | Boolean tables; waivable catalog; override limits; persist unsuccessful assessments | 10.3, 14, 24 | 039–047 | 022,023,053–055 | 007,032 | none | inherit Phase 3 waiver nonwaivables | CLOSED |
| P4-SPEC-004 | P1 | §7.1; §9.3; §23; §25 | Revoke/handoff replacement undefined; implicit reopen | Versioned handoffs; invalidation destinations; CLOSED stays CLOSED | 7, 14.6, 25 | 013,043,044 | 024–026 | 006 | none | do not rewrite BrewSession | CLOSED |
| P4-SPEC-005 | P1 | §15 | Adjacent vs range; subset search; duplicates | Last-three window; max−min ≤ 0.002 SG; no subset skip; golden vectors | 15 | 035 | 018,019 | 005,025 | none | Decimal/ADR-0008 | CLOSED |
| P4-SPEC-006 | P1 | §12–13 | Missing schemas, Plato inverse, ratio vs percent | Type table; adapters; undefined domains | 12, 13, 42 | 025–038,083 | 020,021 | 026 | none | reuse accepted engine, no caller edits | CLOSED |
| P4-SPEC-007 | P1 | §12.2; §23; §25; §42 | Unselected 7-day/CLOSED policy | Canonical time table; inherit Phase 3 §6.8 windows | 18, 24 | 029,030,061 | 020,047 | 026 | none | inherit Phase 3 time | CLOSED |
| P4-SPEC-008 | P1 | §10; §16–17; §21; §29 | Plan mapping, tolerance, revisions, equipment snapshot, deviation identity | Deterministic `phase4-plan-v1`; no revisions; snapshot JSON; deviation UUIDv5 | 10, 16, 22, 29 | 011,046,058 | 027,028,049 | 029 | none | FERMENTATION_FOUNDATION consume-only | CLOSED |
| P4-SPEC-009 | P1 | §20 | FERMENTATION/DRY_HOP timing unnamed | FROM_PITCH minutes from pitched_at; one occurrence; unplanned rules | 21 | 052–057 | 031–033,056 | 031 | none | do not invent competing addition model | CLOSED |
| P4-SPEC-010 | P1 | §11; §28 | Source pair, ownership, cycles, snapshots | Pair agreement; temporal/aborted rules; transactional cycle lock | 11 | 066–070 | 034,035 | 018,027 | none; harvest still deferred | none | CLOSED |
| P4-SPEC-011 | P1 | §30; §32 | Completion vs evidence not serialized | Session lock-before-read; race table R1–R13 | 32 | 073,074 | 036 | 002,028 | none | PostgreSQL authority | CLOSED |
| P4-SPEC-012 | P2 | §30–31 | Per-command scope/canonicalization missing | Command table + idempotency matrix; start scoped to brew_session_id | 30, 31 | 014,071,072 | 004,037 | 001 | none | inherit phase3-operation-v1 | CLOSED |
| P4-SPEC-013 | P2 | §26 | Journal key contradicts Phase 3 order | Merge key `(occurred_at, recorded_at, id)`; closed event vocabulary | 26 | 062,063,065 | 046 | 019 | none | preserve Phase 3 relative order | CLOSED |
| P4-SPEC-014 | P2 | §35–37 | Restore/recovery/perf oracles incomplete | F-REC fixtures; restore vector; Phase 3 reference class + named ops | 35–37 | 078–081 | 029,040,041 | 009–011,016,030 | none | inherit perf class | CLOSED |
| P4-SPEC-015 | P2 | §44–47; §54 | Future-only traceability | Normative §54 mapping; contiguous FR/AC/ADV | 44–47, 54 | 001–087 | 001–056 | 001–033 | none | none | CLOSED |
| P4-SPEC-016 | P2 | §22–25; §27–29 | Non-measurement correction/terminal incomplete | Per-resource correction table; CLOSED/ABORTED matrix | 23, 25 | 031,055,059,064 | 047,048 | 012 | none | inherit Phase 3 terminal pattern | CLOSED |
| P4-SPEC-017 | P3 | §1; §47; §48 | Hard-coded 0003→0004 | Head→head wording; identifier unselected | 1, 47, 48 | 087 | 044 | — | none | inherit round-trip | CLOSED |

`P0_OPEN=0` `P1_OPEN=0` `BLOCKING_P2_OPEN=0` `P3_OPEN=0`

## Root-cause groups

1. **Unselected product policy** treated as inherited by name (OG, time windows, addition timing, plan mapping).
2. **Partial state machines** (pause origin, skip, uniqueness, revocation).
3. **Numeric algorithms** under-specified (stable gravity, adapters, bounds).
4. **Cross-cutting matrices** missing (idempotency per command, concurrency races, terminal allowlists).
5. **Traceability deferred** to a future count-only matrix.

Repair targeted those roots; passing contracts (inventory, a11y, AI, migration, regressions, Phase 5+ leakage) were preserved.

## Exact changes

The Phase 4 specification was replaced in place on the specification branch (same path). Material additions:

- `phase4-entry-v1` with pinned OG consumption, nullable pitch temperature, start scope, abort-then-restart, CLOSED uniqueness.
- Exhaustive session transition table, pause origin, skip destination, abort children, stage cardinality.
- Versioned packaging readiness fields vs prohibited Phase 5 operations.
- `phase4-plan-v1` mapping from sparse/`FERMENTATION_FOUNDATION` sources; default tolerance provenance; no plan revision; equipment JSON snapshot.
- Yeast declaration pair, snapshots, transactional cycle prevention; harvest ops remain deferred.
- Measurement schemas; calculation adapters including Plato inversion of the accepted SG-to-Plato function; attenuation as ratio.
- Completion Boolean tables; unsuccessful assessment persistence; override limits; invalidation without implicit CLOSED reopen.
- `phase4-stable-gravity-v1` last-three full-window algorithm plus Codex golden vectors.
- Canonical time table; late-entry inheritance of Phase 3 §6.8.
- Addition `FROM_PITCH` mapping; closed action enum; zero ledger effect.
- Combined terminal matrix including ABORTED; per-resource correction mutability.
- Per-command API, idempotency, and concurrency matrices.
- Measurable backup/restore, recovery fixtures, performance profile.
- Software safety vs hardware boundary.
- Rebuilt FR/AC/ADV sets and §54 bidirectional mapping; §58 finding closure.

## Finding-by-finding closure

See specification §58. Every P1 and blocking P2 is CLOSED because the disputed behavior now has a single normative algorithm or matrix cell, not additional prose claiming determinism. P3 is CLOSED by removing the provisional `0003→0004` test identity.

## Phase 3 compatibility closure

`PHASE_3_BASELINE_COMPATIBILITY` failed because Phase 4 **consumed** Phase 3 incorrectly, not because Phase 3 files changed. No Phase 0–3 baseline was edited.

| PHASE3_COMPAT_FINDING_ID | ACCEPTED_PHASE3_CONTRACT | PHASE4_CONFLICT | REMEDIATED_PHASE4_BEHAVIOR | STATUS |
|---|---|---|---|---|
| P3C-001 (from P4-SPEC-001) | `ORIGINAL_GRAVITY` is pre-pitch homogenized wort; pitch temperature nullable | Relabel first ferment gravity as OG; reject or synthesize null temperature | Pin current OG leaf or UNKNOWN; never copy ferment gravity; store null temperature as UNKNOWN | CLOSED |
| P3C-002 (from P4-SPEC-013) | Journal order `(occurred_at, recorded_at, id)` | Phase 4 `(occurred_at, sequence)` could reorder Phase 3 events | Same merge key; Phase 4 sequence is not the brew-journal key | CLOSED |
| P3C-003 (from P4-SPEC-009) | FERMENTATION/DRY_HOP excluded from brew-day timing | Inherit “mirror Phase 3” without a mapping | Explicit FROM_PITCH mapping; still zero inventory; leaf correction adapted | CLOSED |
| P3C-004 (from P4-SPEC-007) | §6.8 late-entry 5-minute/24-hour/7-day/30-day | Unselected 7-day measurement policy | Named inheritance mapped to fermentation terminal times | CLOSED |
| P3C-005 | RecipeVersion→BrewSession lineage, pitch handoff, timers, reminders, additions, corrections, waivers, journal, media, inventory, equipment snapshots, calculation authority, security, recovery | Unspecified consumption could mutate meaning | Consume-only references; no Phase 3 row mutation; snapshots for equipment/yeast/OG | CLOSED |

Target `PHASE_3_BASELINE_COMPATIBILITY=PASS` as a Phase 4 consumption verdict.

Inspected and unaltered in Phase 4: RecipeVersion→BrewSession lineage, terminal yeast-pitch handoff schema, Brew-Day measurements, timers, reminders, AdditionEvents, corrections, waivers, journal, media, inventory, equipment, calculation authority, security, recovery.

## Question-resolution table

OPEN_QUESTIONS_ACTUAL originally 14 = 3 declared + 11 implicit (RQ-01–RQ-11).

| QUESTION_ID | QUESTION | WHY_BLOCKING | AVAILABLE_OPTIONS | AUTHORITATIVE_REPOSITORY_EVIDENCE | SELECTED_RESOLUTION | RATIONALE | ADR_REQUIRED | SPEC_SECTIONS_CHANGED | STATUS |
|---|---|---|---|---|---|---|---|---|---|
| P4-OQ-001 | User-wide fermentation cap? | no | cap vs none | original spec default; no PRD cap | no user-wide cap | already selected | NO | 9.1, 53 | CLOSED (non-blocking) |
| P4-OQ-002 | Manual consumption in Phase 4? | no | enable vs defer | ADR-0005/0011; roadmap Phase 6 | deferred | original DEC-003 | YES before enable | 28, 52 | CLOSED (non-blocking) |
| P4-OQ-003 | Mode names | no | enum vs marketing aliases | original §17 | canonical enum | original | NO | 17 | CLOSED (non-blocking) |
| RQ-01 | Missing/corrected OG; null pitch temp | yes | invent OG vs pin vs reject start | Phase 3 measurement table; BrewPitchHandoff null temperature; ADR-0003/0010 | pin leaf / UNKNOWN; accept null temp; explicit reconcile | preserve pre-pitch meaning without editing Phase 3 | NO | 6 | CLOSED |
| RQ-02 | Lifecycle/pause/skip/uniqueness | yes | several graphs | Phase 3 pause-origin pattern; uniqueness defect called out by review | §9 tables | smallest total contract | NO | 9 | CLOSED |
| RQ-03 | Completion predicates | yes | auto vs confirm vs override | Master plan deterministic readiness; Phase 3 waiver policy | Boolean tables + confirm command + limited override | objective PASS/FAIL | NO | 14 | CLOSED |
| RQ-04 | Revoke/handoff current | yes | reopen CLOSED vs invalidate in place | ADR-0003; user no implicit reopen | CLOSED stays CLOSED; versioned handoff | seam-safe | NO | 7, 14.6 | CLOSED |
| RQ-05 | Stable window | yes | adjacent vs range; subset vs last three | review goldens; ADR-0004 | last three; max−min ≤ 0.002 | one answer | NO | 15 | CLOSED |
| RQ-06 | Measurement/calc domains | yes | invent formulas vs adapters | brewing.py; UNITS_AND_ROUNDING; Phase 3 measurement | adapters; hard bounds | no engine fork | NO | 12–13 | CLOSED |
| RQ-07 | Time/late windows | yes | keep 7-day vs inherit Phase 3 | Phase 3 §6.8; Architecture UTC | inherit §6.8 | named inheritance | NO | 18, 24 | CLOSED |
| RQ-08 | Plan/revision/equipment/deviation | yes | revise vs freeze | ADR-0010; RecipeProcessStep sparse schema | freeze plan; snapshot equipment; UUIDv5 deviations | historical reproducibility | NO | 10, 22, 29 | CLOSED |
| RQ-09 | Addition timing/repeat | yes | several epochs | Phase 3 exclusion table; RecipeIngredient timing_minutes | FROM_PITCH; one occurrence | does not guess brew-day semantics | NO | 21 | CLOSED |
| RQ-10 | Yeast source relation | yes | notes vs constrained graph | Domain lineage; security ownership; DEC-004 defer ops | declaration pair + cycle lock | bounded, no harvest ops | NO | 11 | CLOSED |
| RQ-11 | Concurrent completion | yes | lock session vs lock assessment insert | Phase 3 atomic command sets | session lock-before-read | prevents stale READY | NO | 32 | CLOSED |

`OPEN_BLOCKING_QUESTIONS=0`  
`UNRESOLVED_GOVERNANCE_DECISION=` none

## ADR candidate disposition

| ADR_CANDIDATE_ID | DECISION | CURRENT_SPEC_TREATMENT | INDEPENDENT_REVIEW_DISPOSITION | BLOCKS_ACCEPTANCE | SPEC_CLARIFICATION_REQUIRED |
|---|---|---|---|---|---|
| P4-DEC-003 | Inventory consumption on pitch | No Phase 4 consumption; later ADR/phase gate | Keep deferred | NO | NO (clarity already selected; restated in §28) |
| P4-DEC-004 | Yeast harvest/reuse operations | Deferred ops; declaration fields only | Keep ops deferred; fix declaration lineage | NO | YES — declaration pair/cycle/snapshot repaired in §11 without creating harvest operations |

`ADR_BLOCKERS=0`. No new ADR files created.

## New FR / AC / ADV counts

| Family | Original (review) | Remediated |
|---:|---:|---:|
| P4-FR | 67 | **87** (P4-FR-001 through P4-FR-087) |
| P4-AC | 26 | **56** (P4-AC-001 through P4-AC-056, contiguous) |
| P4-ADV | 20 | **33** (P4-ADV-001 through P4-ADV-033) |

`ORPHAN_FR_COUNT=0`  
`ORPHAN_AC_COUNT=0`  
`ORPHAN_ADV_COUNT=0`  

Normative mapping: specification §54.

## Traceability closure

`TRACEABILITY_DESIGN=PASS` (specification design; not implementation evidence).  
`TESTABILITY=PASS` (every FR names a primary executable layer; documentation-only proof forbidden).

## Remaining non-blocking items

- Formal specification acceptance is **not** granted.
- Implementation authorization is **not** granted.
- P4-DEC-003 / P4-DEC-004 remain deferred operational ADRs if those capabilities are later enabled.
- Exact Alembic revision filename remains unselected (P4-SPEC-017).
- Exact HTTP path spelling may vary if command semantics in §30 are implemented.

## Readiness conclusion

Independent Codex re-review is requested against the remediated specification commit and SHA-256 recorded after this artifact is committed.

```
PHASE_4_SPECIFICATION_STATUS=REVIEW_CANDIDATE
PHASE_4_SPECIFICATION_ACCEPTANCE=NOT_YET_GRANTED
PHASE_4_IMPLEMENTATION_AUTHORIZATION=NOT_GRANTED
PHASE_4_IMPLEMENTATION_STARTED=NO
READY_FOR_CODEX_SPECIFICATION_RE_REVIEW=YES
```

(The YES flag is valid only together with the post-commit hash fields in the machine-readable result.)
