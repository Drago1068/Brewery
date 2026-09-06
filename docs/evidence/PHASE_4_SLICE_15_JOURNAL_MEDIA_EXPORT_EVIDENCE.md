# Phase 4 Slice 15 Evidence — JOURNAL_MEDIA_EXPORT

## Baseline identity

| Field | Value |
|---|---|
| Repository | `B:\brewing-platform` |
| Branch | `impl/phase4-fermentation-conditioning-yeast` |
| Input commit | `11b9712ae0d4e4a219f9047e449d62766eba8716` |
| Prior delta review | `docs/evidence/PHASE_4_POST_SLICE_14_DELTA_REVIEW.md` (corrected) |
| Spec baseline | `v0.4.0-phase4-spec` / `bc063d1dac21d3e6b024592e65e2b71256e4df0a` |
| Spec SHA-256 | `EB7CA66F37AF5BD27904A722AE68AEEAEE4C8814C9821E911B8D9CC134F3816D` |
| SPECIFICATION_HASH_VERIFIED | YES |
| SPECIFICATION_CHANGED | NO |
| Slice frontier | `JOURNAL_MEDIA_EXPORT` (final feature implementation slice) |
| Ancestry from `v0.4.0-phase4-spec` | PASS |
| IMPLEMENTATION_BRANCH_BASELINE | PASS |

## Exact normative extraction

| ID | SPEC_SECTION | NORMATIVE_RULE | DEPENDENCIES | PRE-STATUS | MISSING (pre) | SURFACES |
|---|---|---|---|---|---|---|
| P4-FR-062 | §26 | Merge Phase 3+4 journal by `(occurred_at, recorded_at, id)` | writers | PARTIAL/NI | merge export | `journal.py` |
| P4-FR-063 | §26 | Closed event vocabulary | writers | PARTIAL | constant + projection | `JOURNAL_EVENT_TYPES` |
| P4-FR-064 | §27 / §25 | Notes/media under Phase 3 media security | MEDIA_ROOT | NI | notes/attachments | `notes.py`, `media.py`, migration 0015 |
| P4-FR-065 | §26 / §30 | Export JSON/HTML with original+current assessments/handoffs | merge | NI | export routes | `export.py` |
| P4-AC-046 | §45 | Mixed Phase 3 + backdated Phase 4; export twice; stable order | FR-062/065 | — | — | `test_ac046_*` |
| P4-AC-052 | §45 | Malformed media → reject, no row | FR-064 | — | — | `test_ac052_*` |
| P4-ADV-013 | §46 | Polyglot/MIME mismatch → 415/422 | FR-064 | — | — | `test_adv013_*` |
| P4-ADV-019 | §46 | Backdated correction same `occurred_at` → stable merge | FR-062 | — | — | `test_adv019_*` |

Out of scope (FINAL_ACCEPTANCE_ONLY): P4-FR-075, P4-AC-038.

## Authority reuse

Reuses `FermentationJournalEvent` / `BrewJournalEvent`, Phase 3 MIME sniff/quota/`MEDIA_ROOT`, `phase4-operation-v1` idempotency, session OCC, existing assessment/handoff rows, `get_fermentation_session` ownership. No competing journal aggregate.

`EXISTING_PHASE_4_AUTHORITY_REUSED=YES`

## Journal domain / reconstruction

| Concern | Result |
|---|---|
| JOURNAL_DOMAIN_CONTRACT | PASS — append-only projection; dual-time provenance; source_domain PHASE3\|PHASE4 |
| JOURNAL_RECONSTRUCTION | PASS — merge from PostgreSQL/SQLite; no Redis/browser/LLM authority |
| Sort key | `(occurred_at, recorded_at, id)` with coalesce for nulls |
| Fingerprint | `journal_order_fingerprint` for AC-046 stability |

## Media / notes

| Gate | Result |
|---|---|
| MEDIA_ATTACHMENT_MODEL | PASS — `FermentationAttachment` + opaque `MEDIA_ROOT` keys |
| MEDIA_PROVENANCE | PASS — session/stage/actor/operation/sha256; soft-remove preserves history |
| Notes | ≤4000; nonterminal any time; CLOSED/ABORTED ≤7d |
| Upload terminal | DENY when CLOSED/ABORTED |
| Retrieval | ALLOW; missing bytes → `409 MEDIA_UNAVAILABLE` |

## Export

| Gate | Result |
|---|---|
| EXPORT_CONTRACT | PASS — `GET /{id}/export?format=json\|html` |
| EXPORT_CONTENT_INTEGRITY | PASS — session detail + merged journal + notes/attachments + assessment/handoff histories |
| EXPORT_RECONSTRUCTION | PASS — regenerated from DB on each GET |
| HTML | Escaped user text; MEDIA_UNAVAILABLE placeholders |

## Correction / terminal integration

| Gate | Result |
|---|---|
| CORRECTION_HISTORY_INTEGRATION | PASS — merged journal preserves dual-time; export histories include superseded handoffs/assessments |
| TERMINAL_STATE_HISTORY_INTEGRATION | PASS — export/read allowed; upload denied post-terminal; notes within 7d window |

## Security / ownership / idempotency / concurrency

| Gate | Result |
|---|---|
| OWNERSHIP_ISOLATION | PASS — cross-owner export 404 |
| SECURITY_ACCEPTANCE | PASS — MIME/signature/Pillow; closed schemas; no FR-075 matrix campaign |
| IDEMPOTENCY_CONTRACT | PASS — note/media operation_id replay |
| CONCURRENCY_CONTRACT | NOT_APPLICABLE for new export races in this slice (read-only export; OCC on note/media via session revision where supplied) |

## PostgreSQL / migration / API / read model

| Gate | Result |
|---|---|
| POSTGRESQL_ACCEPTANCE | PASS — FKs/indexes; PG suite |
| Migration | `0015_phase4_journal_media_export` revises `0014` |
| MIGRATION_ACCEPTANCE | PASS (upgrade→downgrade→upgrade via `test_phase4_migration`) |
| PHASE_3_MIGRATIONS_UNCHANGED | YES |
| PHASE_3_MIGRATION_ANCESTRY | PASS |
| API_ACCEPTANCE | PASS — notes, attachments, journal, export |
| JOURNAL_MEDIA_EXPORT_READ_MODEL | PASS — detail includes journal/notes/attachments |
| FRONTEND_ACCEPTANCE | NOT_REQUIRED |
| PLAYWRIGHT_ACCEPTANCE | NOT_REQUIRED |

## Yeast / AI / Phase 5

| Gate | Result |
|---|---|
| SLICE_15_YEAST_FEATURE_REQUIREMENTS_CLOSED | 0 |
| YEAST_FEATURE_IMPLEMENTATION_REMAINING | NO (FR-075 FINAL_ACCEPTANCE_ONLY) |
| SLICE_15_AI_AUTHORITY_VIOLATION | NO |
| PHASE_5_PLUS_OPERATIONAL_LEAKAGE | NO |

## Exact AC verification

| AC | Governing FR | Implementation | Test | Result |
|---|---|---|---|---|
| P4-AC-046 | FR-062/065 | merge + fingerprint | `test_ac046_stable_export_order_hash` | PASS |
| P4-AC-052 | FR-064 | media sniff | `test_ac052_malformed_media_rejected` | PASS |

## Exact ADV verification

| ADV_ID | SPEC_FAULT | SETUP | ACTION | EXPECTED | ACTUAL | TEST_ID |
|---|---|---|---|---|---|---|
| P4-ADV-013 | Polyglot/MIME mismatch | ACTIVE session | upload bad MIME/signature | 415/422, no row | Matches | `test_adv013_polyglot_mime_mismatch` |
| P4-ADV-019 | Backdated correction same occurred_at as Phase 3 | Mixed journal | export | Stable merge key | Matches | `test_adv019_backdated_correction_stable_merge` |

## Recovery / regressions

| Gate | Result |
|---|---|
| RECOVERY_ACCEPTANCE | PASS — `test_recovery_reread_note_media` |
| Slice 15 SQLite | PASS (`.pytest-p4s15.txt`) |
| Slice 15 + migration PostgreSQL | PASS (`.pytest-p4s15-pg.txt`) |
| Phase 1A/2/3 + Phase 4 slices 2–15 | PASS (`.pytest-p4s15-reg.txt`) |
| SLICE_11_SERIALIZATION_REGRESSION | PASS |

## Traceability

| ID | Spec → Implementation → Test → Evidence |
|---|---|
| P4-FR-062 | §26 → `journal.merged_journal_events` → AC-046/ADV-019 → this artifact |
| P4-FR-063 | §26 → `JOURNAL_EVENT_TYPES` + writers → `test_fr063_*` → this artifact |
| P4-FR-064 | §27 → notes/media + 0015 → AC-052/ADV-013/FR-064 tests → this artifact |
| P4-FR-065 | §30 → `export.py` → `test_fr065_*` / AC-046 → this artifact |
| P4-AC-046 | §45 → export fingerprint → `test_ac046_*` → this artifact |
| P4-AC-052 | §45 → media sniff → `test_ac052_*` → this artifact |
| P4-ADV-013 | §46 → media sniff → `test_adv013_*` → this artifact |
| P4-ADV-019 | §46 → merge → `test_adv019_*` → this artifact |

`SLICE_15_FR_IMPLEMENTED=4/4`  
`SLICE_15_AC_VERIFIED=2/2`  
`SLICE_15_ADV_VERIFIED=2/2`  
`TRACEABILITY=PASS`

## Self-review

Falsified: cross-owner export; malformed/polyglot media; terminal upload; unstable merge hash; duplicate note operation; missing bytes path; Phase 5 packaging absence; no FR-075/AC-038 feature work; no AI authority.

`IMPLEMENTATION_SELF_REVIEW=PASS`

## Commit discipline

Staged only Slice 15 implementation, migration `0015`, tests, and this evidence. Pre-existing untracked artifacts preserved.

`UNRELATED_FILES_STAGED=NO`  
`PREEXISTING_UNTRACKED_FILES_PRESERVED=YES`
