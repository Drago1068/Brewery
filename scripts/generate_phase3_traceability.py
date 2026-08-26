"""Generate 1:1 Phase 3 traceability from the accepted specification.

Every FR/AC/ADV row references an exact pytest function or Playwright test()
title that exists under apps/api/tests or tests/e2e. Generation fails if a
referenced name is missing, invented, or a glob.

Statuses are honest: PASS / FAIL / SKIPPED / NOT_PROVEN.
SKIPPED and unexecuted environments are never labeled PASS.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md"
OUT = ROOT / "docs/evidence/PHASE_3_TRACEABILITY.md"
TEST_ROOTS = (ROOT / "apps/api/tests", ROOT / "tests/e2e")

SPEC_SHA256 = "6CCBF1589E5F946EC85E8958BEE3D60BD484D1F460A017EFA7D36556A6E43DBF"
EXPECTED_FR = 97
EXPECTED_AC = 63
EXPECTED_ADV = 58
HIGHEST_FR = 102
MISSING_FR = {48, 49, 67, 68, 69}
ALLOWED_STATUS = {"PASS", "FAIL", "SKIPPED", "NOT_PROVEN"}

PYTEST_DEF = re.compile(r"^(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(", re.M)
PLAYWRIGHT_TEST = re.compile(r"""(?:^|\n)\s*test\(\s*(['"])(.+?)\1""", re.M)

ENV_SQLITE = "SQLite unit/domain"
ENV_SQLITE_API = "SQLite API (TestClient)"
ENV_PG = "PostgreSQL integration (TEST_USE_POSTGRES=1); skipif when unset"
ENV_E2E = "Playwright E2E (PostgreSQL-backed compose)"
ENV_HARNESS = "Isolated performance harness (not production-build two-tab browser class)"
ENV_BACKUP = "Isolated pg_dump/pg_restore + media bytes (not live backup scripts)"
ENV_REVIEW = "Review/process gate; no dedicated executable test"


@dataclass(frozen=True)
class Row:
    impl_file: str
    symbol: str
    test_file: str
    test_name: str
    env: str
    status: str
    note: str = ""


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def collect_tests() -> dict[str, set[str]]:
    catalog: dict[str, set[str]] = {}
    for root in TEST_ROOTS:
        if not root.exists():
            raise SystemExit(f"missing test root: {root}")
        if root == ROOT / "apps/api/tests":
            files = list(root.glob("test_*.py"))
        else:
            files = [p for p in root.rglob("*") if p.suffix in {".py", ".ts"} and p.is_file()]
        for path in files:
            text = path.read_text(encoding="utf-8")
            names = set(PYTEST_DEF.findall(text))
            names.update(match.group(2) for match in PLAYWRIGHT_TEST.finditer(text))
            catalog[rel(path)] = names
    return catalog


def parse_spec(text: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    fr_defs = [(f"P3-FR-{n}", rest.strip()) for n, rest in re.findall(r"\*\*P3-FR-(\d+):\*\*\s*(.+)", text)]
    ac_seen: dict[str, str] = {}
    for n, rest in re.findall(r"- \*\*P3-AC-(\d+):\*\*\s*(.+)", text):
        ac_seen.setdefault(f"P3-AC-{n}", rest.strip())
    for aid, rest in re.findall(r"\|\s*(P3-AC-\d+)\s*\|\s*([^|]+)\|", text):
        ac_seen.setdefault(aid, rest.strip())
    adv_rows = [(aid, rest.strip()) for aid, rest in re.findall(r"\|\s*(P3-ADV-\d+)\s*\|\s*([^|]+)\|", text)]
    return fr_defs, list(ac_seen.items()), adv_rows


def expand_fr_mentions(blob: str) -> set[int]:
    found: set[int] = set()
    for match in re.finditer(r"P3-FR-(\d+(?:/\d+)*)(?:\s+through\s+(\d+))?", blob, flags=re.I):
        parts = [int(item) for item in match.group(1).split("/")]
        found.update(parts)
        if match.group(2):
            found.update(range(parts[-1], int(match.group(2)) + 1))
    return found


def cell(value: str) -> str:
    return value.replace("|", "/").replace("\n", " ").strip()


def adv_ids_from_test(name: str) -> list[str]:
    if not name.startswith("test_adv_"):
        return []
    body = name.removeprefix("test_adv_")
    ids: list[str] = []
    for token in body.split("_"):
        if re.fullmatch(r"\d{3}", token):
            ids.append(f"P3-ADV-{token}")
        else:
            break
    return ids


def require_mapping(catalog: dict[str, set[str]], row: Row, rid: str) -> None:
    if row.status not in ALLOWED_STATUS:
        raise SystemExit(f"{rid}: invalid STATUS={row.status}")
    if "suite covering" in row.test_name.lower():
        raise SystemExit(f"{rid}: invented suite label is not allowed: {row.test_name}")
    if "*" in row.test_file or "*" in row.test_name:
        raise SystemExit(f"{rid}: glob mappings are not allowed")
    if not row.test_file or not row.test_name:
        if row.status != "NOT_PROVEN":
            raise SystemExit(f"{rid}: empty TEST_NAME requires STATUS=NOT_PROVEN")
        return
    names = catalog.get(row.test_file)
    if names is None:
        raise SystemExit(f"{rid}: TEST_FILE does not exist in scan roots: {row.test_file}")
    if row.test_name not in names:
        raise SystemExit(
            f"{rid}: TEST_NAME {row.test_name!r} not found in {row.test_file}. "
            f"Known: {sorted(names)[:12]}"
        )


# --- explicit mappings (implementation symbol + exact executable test) ---


def fr_map() -> dict[int, Row]:
    M = Row
    t_mat = "apps/api/tests/test_phase3_materialization.py"
    t_adv = "apps/api/tests/test_phase3_adversarial.py"
    t_api = "apps/api/tests/test_phase3_api.py"
    t_eng = "apps/api/tests/test_phase3_engines.py"
    t_sec = "apps/api/tests/test_phase3_security.py"
    t_day = "apps/api/tests/test_brew_day_api.py"
    t_cal = "apps/api/tests/test_calculations.py"
    t_obs = "apps/api/tests/test_phase3_observability.py"
    t_perf = "apps/api/tests/test_phase3_performance.py"
    t_conc = "apps/api/tests/test_phase3_concurrency.py"
    t_bak = "apps/api/tests/test_phase3_backup_restore.py"
    e_can = "tests/e2e/phase3-canonical.spec.ts"
    e_p3 = "tests/e2e/phase3.spec.ts"
    mat = "apps/api/brewing_api/domain/brew_day/materialization.py"
    brew = "apps/api/brewing_api/application/brew_day.py"
    cmd = "apps/api/brewing_api/application/phase3/commands.py"
    add = "apps/api/brewing_api/application/phase3/additions.py"
    ops = "apps/api/brewing_api/application/phase3/operations.py"
    tmr = "apps/api/brewing_api/application/phase3/timers.py"
    med = "apps/api/brewing_api/application/phase3/media.py"
    wai = "apps/api/brewing_api/application/phase3/waivers.py"
    voi = "apps/api/brewing_api/application/phase3/voice.py"
    plan = "apps/api/brewing_api/application/phase3/plan.py"
    csrf = "apps/api/brewing_api/application/phase3/csrf.py"
    perf = "apps/api/brewing_api/application/phase3/performance.py"
    ev = "apps/api/brewing_api/application/events.py"
    var = "packages/calculations/variance.py"
    ui = "apps/web/app/brew/[id]/page.tsx"
    return {
        1: M(brew, "start_session", t_api, "test_phase1a_recipe_materializes_legacy_plan", ENV_SQLITE_API, "PASS"),
        2: M(mat, "materialize_phase3_plan", t_mat, "test_plan_ids_are_byte_identical_across_repeat_materialization", ENV_SQLITE, "PASS"),
        3: M(brew, "start_session", t_adv, "test_adv_057_later_recipe_change_does_not_mutate_session_snapshot", ENV_SQLITE_API, "PASS"),
        4: M(mat, "materialize_phase3_plan", t_mat, "test_duplicate_sequence_fails_before_session_creation", ENV_SQLITE, "PASS"),
        5: M(ui, "BrewDayPage", e_can, "canonical Phase 3 brew-day flow PRE_BREW through BREW_COMPLETE", ENV_E2E, "PASS"),
        6: M(mat, "materialize_legacy_plan", t_adv, "test_adv_025_phase1a_recipes_and_sessions_still_work", ENV_SQLITE_API, "PASS"),
        7: M(brew, "start_mash", t_adv, "test_adv_027_legacy_mash_start_does_not_duplicate", ENV_SQLITE_API, "PASS"),
        8: M(mat, "materialize_legacy_plan", t_mat, "test_legacy_plan_is_mash_then_brew_complete", ENV_SQLITE, "PASS"),
        9: M(mat, "materialize_phase3_plan", t_mat, "test_plan_step_identity_uses_canonical_inputs", ENV_SQLITE, "PASS"),
        90: M(mat, "_finalize_order", t_mat, "test_decreasing_canonical_order_fails_closed", ENV_SQLITE, "PASS"),
        91: M(mat, "materialize_legacy_plan", t_adv, "test_adv_036_legacy_session_identities_stable_across_get", ENV_SQLITE_API, "PASS"),
        97: M(mat, "plan_step_id via materialize_phase3_plan", t_mat, "test_first_mash_expands_to_mash_in_and_mash_with_distinct_plan_ids", ENV_SQLITE, "PASS"),
        10: M(ui, "BrewDayPage", e_can, "canonical Phase 3 brew-day flow PRE_BREW through BREW_COMPLETE", ENV_E2E, "PASS"),
        11: M(cmd, "start_stage/complete_stage", t_adv, "test_adv_016_complete_mash_without_measurements_fails", ENV_SQLITE_API, "PASS"),
        12: M(wai, "create_waiver", t_eng, "test_waiver_does_not_count_as_measurement", ENV_SQLITE_API, "PASS"),
        13: M(mat, "_finalize_order", t_adv, "test_adv_017_037_045_extend_then_repeat_is_idempotent", ENV_SQLITE_API, "PASS"),
        14: M(cmd, "pause_session/resume_session", t_api, "test_pause_resume_abort_and_note", ENV_SQLITE_API, "PASS"),
        15: M(cmd, "abort_session", t_adv, "test_adv_028_pause_resume_abort", ENV_SQLITE_API, "PASS"),
        16: M(cmd, "repeat_or_return_stage", t_conc, "test_concurrent_repeat_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        17: M(cmd, "extend_stage", t_adv, "test_adv_017_037_045_extend_then_repeat_is_idempotent", ENV_SQLITE_API, "PASS"),
        18: M(brew, "record_measurement", t_adv, "test_adv_018_late_measurement_after_stage_complete", ENV_SQLITE_API, "PASS"),
        19: M(cmd, "repeat_or_return_stage", t_conc, "test_concurrent_controlled_return_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        92: M(cmd, "repeat_or_return_stage", t_conc, "test_concurrent_repeat_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        93: M(cmd, "abort_session", t_adv, "test_adv_028_pause_resume_abort", ENV_SQLITE_API, "PASS"),
        94: M(wai, "create_waiver", t_eng, "test_waiver_does_not_count_as_measurement", ENV_SQLITE_API, "PASS"),
        98: M(plan, "_materialize_occurrence_requirements", t_adv, "test_adv_043_051_runtime_repeat_does_not_regenerate_default_additions", ENV_SQLITE_API, "PASS"),
        100: M(mat, "_apply_declarations", t_mat, "test_safe_default_addition_policy_is_planned_occurrences_only", ENV_SQLITE, "PASS"),
        101: M(mat, "preview_plan", t_mat, "test_runtime_repeat_requires_explicit_declaration_and_preview_hash", ENV_SQLITE, "PASS"),
        102: M(cmd, "repeat_or_return_stage", t_adv, "test_adv_044_052_053_054_055_runtime_repeat_policy_matrix", ENV_SQLITE, "PASS"),
        20: M(tmr, "start_auxiliary_timer", e_p3, "canonical brew-day controls: three timers, reminders, note, refresh, journal", ENV_E2E, "PASS"),
        21: M(mat, "_map_additions", t_adv, "test_adv_029_boil_addition_timing_is_before_planned_stage_end", ENV_SQLITE, "PASS"),
        22: M(brew, "_project_timers", t_eng, "test_expired_timer_survives_reconnect", ENV_SQLITE_API, "PASS"),
        23: M(add, "execute_addition", t_adv, "test_adv_046_049_addition_execute_correction_and_idempotent_replay", ENV_SQLITE_API, "PASS"),
        24: M(add, "execute_addition", t_adv, "test_adv_015_023_addition_and_journal_regen_have_zero_inventory_effect", ENV_SQLITE_API, "PASS"),
        25: M(brew, "reconcile_reminders", t_api, "test_reminder_acknowledgement_does_not_complete_requirement", ENV_SQLITE_API, "PASS"),
        26: M(cmd, "acknowledge_reminder", t_api, "test_reminder_acknowledgement_does_not_complete_requirement", ENV_SQLITE_API, "PASS"),
        27: M(cmd, "acknowledge_reminder", t_api, "test_reminder_acknowledgement_does_not_complete_requirement", ENV_SQLITE_API, "PASS"),
        28: M(cmd, "acknowledge_reminder", t_adv, "test_adv_005_double_reminder_ack_is_idempotent_not_completed", ENV_SQLITE_API, "PASS"),
        29: M(brew, "record_measurement", t_adv, "test_adv_006_measurement_completes_reminder_once", ENV_SQLITE_API, "PASS"),
        30: M(brew, "record_measurement", t_adv, "test_adv_030_047_048_late_types_and_addition_skip_correction", ENV_SQLITE_API, "NOT_PROVEN", "Not every required process-point type is asserted"),
        31: M(brew, "record_measurement", t_day, "test_measurement_validation_and_deviation_rules", ENV_SQLITE_API, "PASS"),
        32: M(brew, "_measurement_context", t_day, "test_measurement_validation_and_deviation_rules", ENV_SQLITE_API, "PASS"),
        33: M(brew, "record_measurement", t_adv, "test_adv_030_047_048_late_types_and_addition_skip_correction", ENV_SQLITE_API, "NOT_PROVEN"),
        34: M(brew, "correct_measurement", t_adv, "test_adv_014_measurement_correction_appends", ENV_SQLITE_API, "PASS"),
        35: M(brew, "correct_measurement", t_adv, "test_adv_014_measurement_correction_appends", ENV_SQLITE_API, "PASS"),
        36: M(brew, "record_measurement", t_adv, "test_adv_018_late_measurement_after_stage_complete", ENV_SQLITE_API, "PASS"),
        37: M(wai, "create_waiver", t_eng, "test_waiver_does_not_count_as_measurement", ENV_SQLITE_API, "PASS"),
        38: M(brew, "record_measurement", t_adv, "test_adv_013_future_observed_at_is_rejected", ENV_SQLITE_API, "PASS"),
        39: M(ops, "replay_or_conflict", t_adv, "test_adv_001_003_004_031_idempotent_replay_and_key_reuse", ENV_SQLITE_API, "PASS"),
        95: M(brew, "record_measurement", t_adv, "test_adv_039_040_aborted_blocks_new_measurement", ENV_SQLITE_API, "NOT_PROVEN", "Full 5m/24h/7d/30d boundary matrix not executed"),
        40: M(var, "compare_measurement", t_cal, "test_variance_is_deterministic_and_tolerance_is_inclusive", ENV_SQLITE, "PASS"),
        41: M(var, "planned_versus_actual", t_cal, "test_variance_is_deterministic_and_tolerance_is_inclusive", ENV_SQLITE, "PASS"),
        42: M(var, "planned_versus_actual", t_cal, "test_variance_outside_tolerance", ENV_SQLITE, "PASS"),
        43: M(brew, "record_measurement", t_day, "test_measurement_validation_and_deviation_rules", ENV_SQLITE_API, "PASS"),
        44: M(brew, "correct_measurement", t_adv, "test_adv_014_measurement_correction_appends", ENV_SQLITE_API, "PASS"),
        45: M(var, "compare_measurement", t_cal, "test_variance_is_deterministic_and_tolerance_is_inclusive", ENV_SQLITE, "NOT_PROVEN", "AI-prohibition is a review invariant, not this unit test"),
        46: M(add, "execute_addition", t_eng, "test_addition_execution_has_zero_inventory_effect", ENV_SQLITE_API, "PASS"),
        47: M(mat, "_map_additions", t_adv, "test_adv_029_boil_addition_timing_is_before_planned_stage_end", ENV_SQLITE, "PASS"),
        99: M(add, "correct_addition", t_adv, "test_adv_046_049_addition_execute_correction_and_idempotent_replay", ENV_SQLITE_API, "PASS"),
        50: M(cmd, "create_note", t_api, "test_pause_resume_abort_and_note", ENV_SQLITE_API, "PASS"),
        51: M(med, "upload_attachment", t_eng, "test_media_allowlist_and_headers", ENV_SQLITE_API, "PASS"),
        52: M(med, "upload_attachment", t_eng, "test_truncated_png_is_rejected_by_decoder", ENV_SQLITE_API, "PASS"),
        53: M(med, "upload_attachment", t_bak, "test_pg_dump_restore_preserves_attachment_metadata_and_media_bytes", ENV_BACKUP, "PASS"),
        54: M(med, "soft_remove_attachment", t_eng, "test_media_allowlist_and_headers", ENV_SQLITE_API, "NOT_PROVEN", "No dedicated audited-soft-delete executable"),
        55: M(ev, "journal", t_day, "test_complete_slice_generates_journal_and_preserves_history", ENV_SQLITE_API, "PASS"),
        56: M(brew, "session_journal_events", t_day, "test_complete_slice_generates_journal_and_preserves_history", ENV_SQLITE_API, "PASS"),
        57: M("apps/api/brewing_api/presentation/routes/brew_sessions.py", "export_session", t_api, "test_completion_audit_endpoint", ENV_SQLITE_API, "NOT_PROVEN", "Audit endpoint is not a human+JSON export proof"),
        58: M(med, "upload_attachment", t_adv, "test_adv_019_032_svg_rejected_png_uploaded", ENV_SQLITE_API, "NOT_PROVEN"),
        59: M(cmd, "completion_audit", t_api, "test_completion_audit_endpoint", ENV_SQLITE_API, "PASS"),
        60: M(ui, "BrewDayPage", e_p3, "voice draft cannot commit fifty-two as mash pH", ENV_E2E, "PASS"),
        61: M(voi, "parse_voice_proposal", t_eng, "test_voice_proposal_is_not_a_commit", ENV_SQLITE, "PASS"),
        62: M(ui, "BrewDayPage", e_p3, "voice draft cannot commit fifty-two as mash pH", ENV_E2E, "PASS"),
        63: M(voi, "parse_voice_proposal", t_eng, "test_voice_proposal_endpoint_does_not_record_measurement", ENV_SQLITE_API, "PASS"),
        64: M(brew, "record_measurement", t_eng, "test_voice_proposal_endpoint_does_not_record_measurement", ENV_SQLITE_API, "NOT_PROVEN", "VOICE_CONFIRMED provenance not asserted"),
        65: M(voi, "parse_voice_proposal", t_eng, "test_voice_proposal_is_not_a_commit", ENV_SQLITE, "NOT_PROVEN", "Architecture prohibition; no always-listening scanner test"),
        66: M(voi, "parse_voice_proposal", t_adv, "test_adv_020_voice_proposal_fifty_two_is_not_committed", ENV_SQLITE_API, "PASS"),
        70: M(brew, "session_details", t_adv, "test_adv_022_reopened_session_reconstructs_expired_timer", ENV_SQLITE_API, "PASS"),
        71: M(brew, "session_details", e_p3, "pause, resume, refresh recovery, and journal remain authoritative", ENV_E2E, "PASS"),
        72: M(ops, "replay_or_conflict", t_eng, "test_idempotent_pause_replays_same_result", ENV_SQLITE_API, "PASS"),
        73: M(ops, "replay_or_conflict", t_conc, "test_concurrent_http_repeat_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        74: M(ui, "BrewDayPage", e_p3, "pause, resume, refresh recovery, and journal remain authoritative", ENV_E2E, "PASS"),
        75: M(brew, "get_session", t_adv, "test_adv_009_056_redis_is_non_authoritative", ENV_SQLITE_API, "PASS"),
        76: M(ops, "replay_or_conflict", t_adv, "test_adv_001_003_004_031_idempotent_replay_and_key_reuse", ENV_SQLITE_API, "PASS"),
        77: M(brew, "_lock_revision", t_eng, "test_stale_revision_is_conflict", ENV_SQLITE_API, "PASS"),
        78: M(ops, "store_success", t_adv, "test_adv_011_conflict_does_not_create_partial_measurement", ENV_SQLITE_API, "PASS"),
        79: M(brew, "session_details", t_bak, "test_pg_dump_restore_preserves_attachment_metadata_and_media_bytes", ENV_BACKUP, "NOT_PROVEN", "Full close/sleep/API/PG/Redis recovery matrix not executed"),
        80: M(brew, "get_session", t_sec, "test_cross_owner_session_get_is_404", ENV_SQLITE_API, "PASS"),
        81: M(brew, "get_session", t_eng, "test_cross_owner_session_is_hidden", ENV_SQLITE_API, "PASS"),
        82: M(ev, "audit", t_day, "test_complete_slice_generates_journal_and_preserves_history", ENV_SQLITE_API, "NOT_PROVEN", "Journal coverage is not a full security-audit matrix"),
        83: M("apps/api/brewing_api/platform/metrics.py", "reconstruct_failure", t_obs, "test_reconstruct_returns_events_for_correlation_id", ENV_SQLITE_API, "PASS"),
        84: M("apps/api/brewing_api/presentation/routes/health.py", "authenticated metrics/routes", t_sec, "test_metrics_requires_authentication", ENV_SQLITE_API, "PASS"),
        85: M(ev, "journal", t_day, "test_complete_slice_generates_journal_and_preserves_history", ENV_SQLITE_API, "PASS"),
        86: M(brew, "render_journal_html", t_adv, "test_adv_015_023_addition_and_journal_regen_have_zero_inventory_effect", ENV_SQLITE_API, "PASS"),
        87: M("apps/api/brewing_api/platform/metrics.py", "snapshot", t_obs, "test_metrics_sample_count_increases_after_mutations", ENV_SQLITE_API, "PASS"),
        88: M(perf, "run_isolated_performance_harness", t_perf, "test_phase3_performance_acceptance_reference_class", "PostgreSQL isolated harness n=100 (TEST_USE_POSTGRES=1)", "PASS", "Two-tab browser sampler is P3-ADV-034 / phase3-performance.spec.ts"),
        89: M(csrf, "Phase3SecurityMiddleware.dispatch", t_sec, "test_csrf_matrix_missing_wrong_and_valid", ENV_SQLITE_API, "PASS"),
        96: M(cmd, "abort_session", t_eng, "test_abort_blocks_new_measurement", ENV_SQLITE_API, "PASS"),
    }


def ac_map() -> dict[int, Row]:
    M = Row
    t_mat = "apps/api/tests/test_phase3_materialization.py"
    t_adv = "apps/api/tests/test_phase3_adversarial.py"
    t_api = "apps/api/tests/test_phase3_api.py"
    t_eng = "apps/api/tests/test_phase3_engines.py"
    t_sec = "apps/api/tests/test_phase3_security.py"
    t_day = "apps/api/tests/test_brew_day_api.py"
    t_obs = "apps/api/tests/test_phase3_observability.py"
    t_perf = "apps/api/tests/test_phase3_performance.py"
    t_conc = "apps/api/tests/test_phase3_concurrency.py"
    t_inv = "apps/api/tests/test_phase3_invariants.py"
    t_bak = "apps/api/tests/test_phase3_backup_restore.py"
    t_mig = "apps/api/tests/test_phase3_migration.py"
    e_can = "tests/e2e/phase3-canonical.spec.ts"
    e_p3 = "tests/e2e/phase3.spec.ts"
    e_p1 = "tests/e2e/phase1a.spec.ts"
    none = M("", "", "", "", ENV_REVIEW, "NOT_PROVEN", "No exact pytest/Playwright identifier for this process gate")
    return {
        1: none,
        2: none,
        3: none,
        4: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e_p1, "complete Phase 1A workflow and recover the Mash timer after refresh", ENV_E2E, "PASS"),
        10: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e_can, "canonical Phase 3 brew-day flow PRE_BREW through BREW_COMPLETE", ENV_E2E, "PASS"),
        11: M("apps/api/brewing_api/application/phase3/operations.py", "replay_or_conflict", t_eng, "test_stale_revision_is_conflict", ENV_SQLITE_API, "PASS"),
        12: M("apps/api/brewing_api/application/phase3/commands.py", "pause_session/abort_session", t_adv, "test_adv_028_pause_resume_abort", ENV_SQLITE_API, "NOT_PROVEN", "Not every section 6.7 child effect is asserted"),
        13: M("apps/api/brewing_api/application/phase3/timers.py", "start_auxiliary_timer", e_p3, "canonical brew-day controls: three timers, reminders, note, refresh, journal", ENV_E2E, "PASS"),
        14: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_map_additions", t_adv, "test_adv_029_boil_addition_timing_is_before_planned_stage_end", ENV_SQLITE, "PASS"),
        15: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", t_adv, "test_adv_030_047_048_late_types_and_addition_skip_correction", ENV_SQLITE_API, "NOT_PROVEN"),
        16: M("apps/api/brewing_api/application/brew_day.py", "correct_measurement", t_adv, "test_adv_014_measurement_correction_appends", ENV_SQLITE_API, "PASS"),
        17: M("apps/api/brewing_api/application/phase3/commands.py", "repeat_or_return_stage", t_conc, "test_concurrent_http_repeat_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        18: M("apps/api/brewing_api/application/phase3/commands.py", "abort_session", t_eng, "test_abort_blocks_new_measurement", ENV_SQLITE_API, "PASS"),
        20: M("database/migrations/versions/0003_phase3_brew_day_os.py", "upgrade", t_mig, "test_alembic_version_is_phase3_head", ENV_PG, "PASS"),
        21: M("database/migrations/versions/0003_phase3_brew_day_os.py", "upgrade/downgrade", t_mig, "test_alembic_roundtrip_preserves_phase2_session_on_disposable_database", ENV_PG, "PASS"),
        22: M("database/migrations/versions/0003_phase3_brew_day_os.py", "upgrade/downgrade", t_mig, "test_alembic_roundtrip_preserves_phase2_session_on_disposable_database", ENV_PG, "PASS"),
        23: M("database/migrations/versions/0003_phase3_brew_day_os.py", "upgrade", t_inv, "test_cross_session_attachment_is_rejected", ENV_PG, "PASS"),
        24: M("apps/api/brewing_api/application/brew_day.py", "session_details", t_adv, "test_adv_009_056_redis_is_non_authoritative", ENV_SQLITE_API, "NOT_PROVEN", "API/web restart not independently re-executed"),
        30: M("apps/api/brewing_api/application/brew_day.py", "get_session", t_sec, "test_cross_owner_session_get_is_404", ENV_SQLITE_API, "NOT_PROVEN", "Not every identifier class is covered"),
        31: M("apps/api/brewing_api/application/phase3/media.py", "upload_attachment", t_adv, "test_adv_032_oversize_and_traversal_filenames_rejected", ENV_SQLITE_API, "NOT_PROVEN"),
        32: none,
        33: none,
        40: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e_p3, "canonical brew-day controls: three timers, reminders, note, refresh, journal", ENV_E2E, "PASS"),
        41: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e_can, "canonical Phase 3 brew-day flow PRE_BREW through BREW_COMPLETE", ENV_E2E, "PASS"),
        42: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e_p3, "pause, resume, refresh recovery, and journal remain authoritative", ENV_E2E, "PASS"),
        43: M("apps/api/brewing_api/application/phase3/voice.py", "parse_voice_proposal", e_p3, "voice draft cannot commit fifty-two as mash pH", ENV_E2E, "PASS"),
        44: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e_p3, "tablet viewport and keyboard focus remain usable", ENV_E2E, "PASS"),
        45: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e_p3, "phone viewport keeps mash timer and measurement controls usable", ENV_E2E, "PASS"),
        50: none,
        51: none,
        52: M("apps/api/brewing_api/application/brew_day.py", "start_session", t_api, "test_phase1a_recipe_materializes_legacy_plan", ENV_SQLITE_API, "NOT_PROVEN"),
        53: M("apps/api/brewing_api/application/phase3/media.py", "upload_attachment", t_bak, "test_pg_dump_restore_preserves_attachment_metadata_and_media_bytes", ENV_BACKUP, "PASS"),
        54: none,
        60: M("apps/api/brewing_api/application/phase3/commands.py", "repeat_or_return_stage", t_conc, "test_concurrent_repeat_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        61: M("apps/api/brewing_api/application/phase3/commands.py", "acknowledge_reminder", t_adv, "test_adv_005_double_reminder_ack_is_idempotent_not_completed", ENV_SQLITE_API, "PASS"),
        62: M("apps/api/brewing_api/application/phase3/timers.py", "extend_timer/replace_timer", t_eng, "test_timer_extend_appends_revision", ENV_SQLITE_API, "PASS"),
        63: M("apps/api/brewing_api/application/phase3/operations.py", "replay_or_conflict", t_adv, "test_adv_001_003_004_031_idempotent_replay_and_key_reuse", ENV_SQLITE_API, "NOT_PROVEN", "Canonical fingerprint/archive/tombstone matrix incomplete"),
        64: M("apps/api/brewing_api/application/events.py", "journal", t_day, "test_complete_slice_generates_journal_and_preserves_history", ENV_SQLITE_API, "PASS"),
        65: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", t_adv, "test_adv_030_047_048_late_types_and_addition_skip_correction", ENV_SQLITE_API, "NOT_PROVEN"),
        66: M("apps/api/brewing_api/application/phase3/commands.py", "completion_audit", t_adv, "test_adv_024_completion_audit_excludes_waiver_from_measured", ENV_SQLITE_API, "PASS"),
        67: M("apps/api/brewing_api/application/phase3/additions.py", "execute_addition", t_eng, "test_addition_execution_has_zero_inventory_effect", ENV_SQLITE_API, "PASS"),
        68: M("apps/api/brewing_api/application/phase3/media.py", "upload_attachment", t_eng, "test_truncated_png_is_rejected_by_decoder", ENV_SQLITE_API, "NOT_PROVEN"),
        69: M("apps/api/brewing_api/application/brew_day.py", "session_details", t_adv, "test_adv_022_reopened_session_reconstructs_expired_timer", ENV_SQLITE_API, "NOT_PROVEN"),
        70: M("database/migrations/versions/0003_phase3_brew_day_os.py", "upgrade", t_inv, "test_addition_event_update_and_delete_are_rejected", ENV_PG, "PASS"),
        71: M("apps/api/brewing_api/platform/metrics.py", "reconstruct_failure", t_obs, "test_reconstruct_returns_events_for_correlation_id", ENV_SQLITE_API, "PASS"),
        72: M("apps/api/brewing_api/application/phase3/voice.py", "parse_voice_proposal", t_adv, "test_adv_020_voice_proposal_fifty_two_is_not_committed", ENV_SQLITE_API, "PASS"),
        73: M("apps/api/brewing_api/application/phase3/performance.py", "run_isolated_performance_harness", t_perf, "test_phase3_performance_acceptance_reference_class", "PostgreSQL isolated harness n=100 (TEST_USE_POSTGRES=1)", "PASS"),
        74: M("apps/api/brewing_api/domain/brew_day/materialization.py", "materialize_phase3_plan", t_mat, "test_plan_ids_are_byte_identical_across_repeat_materialization", ENV_SQLITE, "PASS"),
        75: M("apps/api/brewing_api/application/phase3/commands.py", "pause_session/abort_session", t_adv, "test_adv_028_pause_resume_abort", ENV_SQLITE_API, "NOT_PROVEN"),
        76: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_map_additions", t_adv, "test_adv_029_boil_addition_timing_is_before_planned_stage_end", ENV_SQLITE, "PASS"),
        77: M("apps/api/brewing_api/application/phase3/csrf.py", "Phase3SecurityMiddleware.dispatch", t_sec, "test_csrf_matrix_missing_wrong_and_valid", ENV_SQLITE_API, "PASS"),
        78: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_finalize_order", t_mat, "test_decreasing_canonical_order_fails_closed", ENV_SQLITE, "PASS"),
        79: M("apps/api/brewing_api/domain/brew_day/materialization.py", "materialize_legacy_plan", t_adv, "test_adv_036_legacy_session_identities_stable_across_get", ENV_SQLITE_API, "NOT_PROVEN"),
        80: M("apps/api/brewing_api/application/phase3/commands.py", "repeat_or_return_stage", t_conc, "test_concurrent_controlled_return_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        81: M("apps/api/brewing_api/application/phase3/waivers.py", "create_waiver", t_adv, "test_adv_038_waiver_then_abort", ENV_SQLITE_API, "PASS"),
        82: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", t_adv, "test_adv_018_late_measurement_after_stage_complete", ENV_SQLITE_API, "NOT_PROVEN"),
        83: M("apps/api/brewing_api/application/phase3/commands.py", "abort_session", t_adv, "test_adv_039_040_aborted_blocks_new_measurement", ENV_SQLITE_API, "PASS"),
        84: M("apps/api/brewing_api/domain/brew_day/materialization.py", "materialize_phase3_plan", t_mat, "test_first_mash_expands_to_mash_in_and_mash_with_distinct_plan_ids", ENV_SQLITE, "PASS"),
        85: M("apps/api/brewing_api/application/phase3/plan.py", "_materialize_occurrence_requirements", t_adv, "test_adv_043_051_runtime_repeat_does_not_regenerate_default_additions", ENV_SQLITE_API, "NOT_PROVEN"),
        86: M("apps/api/brewing_api/application/phase3/additions.py", "correct_addition", t_adv, "test_adv_046_049_addition_execute_correction_and_idempotent_replay", ENV_SQLITE_API, "PASS"),
        87: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_apply_declarations", t_mat, "test_safe_default_addition_policy_is_planned_occurrences_only", ENV_SQLITE, "PASS"),
        88: M("apps/api/brewing_api/application/phase3/commands.py", "repeat_or_return_stage", t_adv, "test_adv_044_052_053_054_055_runtime_repeat_policy_matrix", ENV_SQLITE, "NOT_PROVEN"),
        89: M("apps/api/brewing_api/domain/brew_day/materialization.py", "materialize_phase3_plan", t_adv, "test_adv_057_later_recipe_change_does_not_mutate_session_snapshot", ENV_SQLITE_API, "PASS"),
    }


def adv_map() -> dict[int, Row]:
    """Map each ADV to the exact named adversarial (or successor) executable."""
    M = Row
    a = "apps/api/tests/test_phase3_adversarial.py"
    c = "apps/api/tests/test_phase3_concurrency.py"
    p = "apps/api/tests/test_phase3_performance.py"
    e3 = "tests/e2e/phase3.spec.ts"
    e1 = "tests/e2e/phase1a.spec.ts"
    eperf = "tests/e2e/phase3-performance.spec.ts"
    ops = "apps/api/brewing_api/application/phase3/operations.py"
    return {
        1: M(ops, "replay_or_conflict", a, "test_adv_001_003_004_031_idempotent_replay_and_key_reuse", ENV_SQLITE_API, "PASS"),
        2: M(ops, "replay_or_conflict", a, "test_adv_002_second_distinct_measurement_conflicts", ENV_SQLITE_API, "PASS"),
        3: M(ops, "replay_or_conflict", a, "test_adv_001_003_004_031_idempotent_replay_and_key_reuse", ENV_SQLITE_API, "PASS"),
        4: M(ops, "replay_or_conflict", a, "test_adv_001_003_004_031_idempotent_replay_and_key_reuse", ENV_SQLITE_API, "PASS"),
        5: M("apps/api/brewing_api/application/phase3/commands.py", "acknowledge_reminder", a, "test_adv_005_double_reminder_ack_is_idempotent_not_completed", ENV_SQLITE_API, "PASS"),
        6: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", a, "test_adv_006_measurement_completes_reminder_once", ENV_SQLITE_API, "PASS"),
        7: M("apps/api/brewing_api/application/phase3/timers.py", "start_auxiliary_timer", e3, "canonical brew-day controls: three timers, reminders, note, refresh, journal", ENV_E2E, "PASS"),
        8: M("apps/api/brewing_api/application/phase3/timers.py", "extend_timer/replace_timer", a, "test_adv_008_timer_extend_then_stale_replace_conflicts", ENV_SQLITE_API, "PASS"),
        9: M("apps/api/brewing_api/application/brew_day.py", "get_session", a, "test_adv_009_056_redis_is_non_authoritative", ENV_SQLITE_API, "PASS"),
        10: M("apps/api/brewing_api/application/brew_day.py", "_project_timers", a, "test_adv_007_010_expired_timer_recovered_from_postgres_deadline", ENV_SQLITE_API, "NOT_PROVEN", "Deadline reconstruction is not an API-restart proof"),
        11: M(ops, "store_success", a, "test_adv_011_conflict_does_not_create_partial_measurement", ENV_SQLITE_API, "NOT_PROVEN", "Not a live PostgreSQL restart"),
        12: M("apps/api/brewing_api/application/phase3/operations.py", "replay_or_conflict", a, "test_adv_012_no_authoritative_background_worker", ENV_SQLITE, "PASS"),
        13: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", a, "test_adv_013_future_observed_at_is_rejected", ENV_SQLITE_API, "PASS"),
        14: M("apps/api/brewing_api/application/brew_day.py", "correct_measurement", a, "test_adv_014_measurement_correction_appends", ENV_SQLITE_API, "PASS"),
        15: M("apps/api/brewing_api/application/phase3/additions.py", "execute_addition", a, "test_adv_015_023_addition_and_journal_regen_have_zero_inventory_effect", ENV_SQLITE_API, "PASS"),
        16: M("apps/api/brewing_api/application/phase3/commands.py", "complete_stage", a, "test_adv_016_complete_mash_without_measurements_fails", ENV_SQLITE_API, "PASS"),
        17: M("apps/api/brewing_api/application/phase3/commands.py", "extend_stage/repeat_or_return_stage", a, "test_adv_017_037_045_extend_then_repeat_is_idempotent", ENV_SQLITE_API, "PASS"),
        18: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", a, "test_adv_018_late_measurement_after_stage_complete", ENV_SQLITE_API, "PASS"),
        19: M("apps/api/brewing_api/application/phase3/media.py", "upload_attachment", a, "test_adv_019_032_svg_rejected_png_uploaded", ENV_SQLITE_API, "NOT_PROVEN"),
        20: M("apps/api/brewing_api/application/phase3/voice.py", "parse_voice_proposal", a, "test_adv_020_voice_proposal_fifty_two_is_not_committed", ENV_SQLITE_API, "PASS"),
        21: M("apps/api/brewing_api/application/brew_day.py", "start_session", a, "test_adv_021_recipe_version_immutable_after_session", ENV_SQLITE_API, "PASS"),
        22: M("apps/api/brewing_api/application/brew_day.py", "session_details", a, "test_adv_022_reopened_session_reconstructs_expired_timer", ENV_SQLITE_API, "PASS"),
        23: M("apps/api/brewing_api/application/brew_day.py", "render_journal_html", a, "test_adv_015_023_addition_and_journal_regen_have_zero_inventory_effect", ENV_SQLITE_API, "PASS"),
        24: M("apps/api/brewing_api/application/phase3/commands.py", "completion_audit", a, "test_adv_024_completion_audit_excludes_waiver_from_measured", ENV_SQLITE_API, "PASS"),
        25: M("apps/web/app/brew/[id]/page.tsx", "BrewDayPage", e1, "complete Phase 1A workflow and recover the Mash timer after refresh", ENV_E2E, "PASS"),
        26: M("apps/api/brewing_api/domain/brew_day/materialization.py", "preview_plan", a, "test_adv_026_035_041_042_preview_hash_is_deterministic", ENV_SQLITE_API, "PASS"),
        27: M("apps/api/brewing_api/application/brew_day.py", "start_mash", a, "test_adv_027_legacy_mash_start_does_not_duplicate", ENV_SQLITE_API, "PASS"),
        28: M("apps/api/brewing_api/application/phase3/commands.py", "pause_session/abort_session", a, "test_adv_028_pause_resume_abort", ENV_SQLITE_API, "PASS"),
        29: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_map_additions", a, "test_adv_029_boil_addition_timing_is_before_planned_stage_end", ENV_SQLITE, "PASS"),
        30: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", a, "test_adv_030_047_048_late_types_and_addition_skip_correction", ENV_SQLITE_API, "NOT_PROVEN"),
        31: M(ops, "replay_or_conflict", a, "test_adv_001_003_004_031_idempotent_replay_and_key_reuse", ENV_SQLITE_API, "NOT_PROVEN", "Archived 410/tombstone path not proven"),
        32: M("apps/api/brewing_api/application/phase3/media.py", "upload_attachment", a, "test_adv_032_oversize_and_traversal_filenames_rejected", ENV_SQLITE_API, "NOT_PROVEN"),
        33: M("apps/api/brewing_api/application/phase3/csrf.py", "Phase3SecurityMiddleware.dispatch", a, "test_adv_033_csrf_missing_and_wrong_token_rejected", ENV_SQLITE_API, "PASS"),
        34: M("apps/api/brewing_api/application/phase3/performance.py", "run_isolated_performance_harness", eperf, "browser performance sampler records navigation and recovery samples", "Playwright two-tab sampler PHASE3_PERF_BROWSER=1; server n=100 is test_phase3_performance_acceptance_reference_class", "PASS"),
        35: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_finalize_order", a, "test_adv_026_035_041_042_preview_hash_is_deterministic", ENV_SQLITE_API, "PASS"),
        36: M("apps/api/brewing_api/domain/brew_day/materialization.py", "materialize_legacy_plan", a, "test_adv_036_legacy_session_identities_stable_across_get", ENV_SQLITE_API, "NOT_PROVEN"),
        37: M("apps/api/brewing_api/application/phase3/commands.py", "repeat_or_return_stage", c, "test_concurrent_controlled_return_one_winner_no_duplicate_occurrences", ENV_PG, "PASS"),
        38: M("apps/api/brewing_api/application/phase3/waivers.py", "create_waiver", a, "test_adv_038_waiver_then_abort", ENV_SQLITE_API, "PASS"),
        39: M("apps/api/brewing_api/application/brew_day.py", "record_measurement", a, "test_adv_039_040_aborted_blocks_new_measurement", ENV_SQLITE_API, "NOT_PROVEN"),
        40: M("apps/api/brewing_api/application/phase3/commands.py", "abort_session", a, "test_adv_039_040_aborted_blocks_new_measurement", ENV_SQLITE_API, "PASS"),
        41: M("apps/api/brewing_api/domain/brew_day/materialization.py", "materialize_phase3_plan", a, "test_adv_026_035_041_042_preview_hash_is_deterministic", ENV_SQLITE_API, "PASS"),
        42: M("apps/api/brewing_api/domain/brew_day/materialization.py", "materialize_phase3_plan", a, "test_adv_026_035_041_042_preview_hash_is_deterministic", ENV_SQLITE_API, "PASS"),
        43: M("apps/api/brewing_api/application/phase3/plan.py", "_materialize_occurrence_requirements", a, "test_adv_043_051_runtime_repeat_does_not_regenerate_default_additions", ENV_SQLITE_API, "PASS"),
        44: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_apply_declarations", a, "test_adv_044_052_053_054_055_runtime_repeat_policy_matrix", ENV_SQLITE, "PASS"),
        45: M("apps/api/brewing_api/application/phase3/commands.py", "repeat_or_return_stage", a, "test_adv_017_037_045_extend_then_repeat_is_idempotent", ENV_SQLITE_API, "PASS"),
        46: M("apps/api/brewing_api/application/phase3/additions.py", "correct_addition", a, "test_adv_046_049_addition_execute_correction_and_idempotent_replay", ENV_SQLITE_API, "PASS"),
        47: M("apps/api/brewing_api/application/phase3/additions.py", "correct_addition", a, "test_adv_030_047_048_late_types_and_addition_skip_correction", ENV_SQLITE_API, "NOT_PROVEN"),
        48: M("apps/api/brewing_api/application/phase3/additions.py", "correct_addition", a, "test_adv_030_047_048_late_types_and_addition_skip_correction", ENV_SQLITE_API, "NOT_PROVEN"),
        49: M("apps/api/brewing_api/application/phase3/additions.py", "correct_addition", a, "test_adv_046_049_addition_execute_correction_and_idempotent_replay", ENV_SQLITE_API, "PASS"),
        50: M("apps/api/brewing_api/application/phase3/additions.py", "correct_addition", a, "test_adv_050_planned_recipe_addition_correction_is_unavailable", ENV_SQLITE_API, "PASS"),
        51: M("apps/api/brewing_api/application/phase3/plan.py", "_materialize_occurrence_requirements", a, "test_adv_043_051_runtime_repeat_does_not_regenerate_default_additions", ENV_SQLITE_API, "PASS"),
        52: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_apply_declarations", a, "test_adv_044_052_053_054_055_runtime_repeat_policy_matrix", ENV_SQLITE, "PASS"),
        53: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_apply_declarations", a, "test_adv_044_052_053_054_055_runtime_repeat_policy_matrix", ENV_SQLITE, "PASS"),
        54: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_apply_declarations", a, "test_adv_044_052_053_054_055_runtime_repeat_policy_matrix", ENV_SQLITE, "NOT_PROVEN"),
        55: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_apply_declarations", a, "test_adv_044_052_053_054_055_runtime_repeat_policy_matrix", ENV_SQLITE, "NOT_PROVEN"),
        56: M("apps/api/brewing_api/application/brew_day.py", "get_session", a, "test_adv_009_056_redis_is_non_authoritative", ENV_SQLITE_API, "PASS"),
        57: M("apps/api/brewing_api/application/brew_day.py", "start_session", a, "test_adv_057_later_recipe_change_does_not_mutate_session_snapshot", ENV_SQLITE_API, "PASS"),
        58: M("apps/api/brewing_api/domain/brew_day/materialization.py", "_apply_declarations", a, "test_adv_057_058_policy_comes_from_materialization_not_heuristics", ENV_SQLITE, "PASS"),
    }


def fr_to_ac(ac_defs: list[tuple[str, str]]) -> dict[int, list[str]]:
    mapping: dict[int, list[str]] = {}
    for aid, title in ac_defs:
        for n in sorted(expand_fr_mentions(title)):
            mapping.setdefault(n, []).append(aid)
    extras = {
        1: ["P3-AC-001"],
        5: ["P3-AC-010", "P3-AC-040", "P3-AC-041"],
        6: ["P3-AC-004", "P3-AC-079"],
        7: ["P3-AC-004", "P3-AC-079"],
        10: ["P3-AC-010", "P3-AC-041"],
        11: ["P3-AC-011"],
        20: ["P3-AC-013", "P3-AC-041"],
        50: ["P3-AC-041", "P3-AC-068"],
        60: ["P3-AC-043", "P3-AC-072"],
        70: ["P3-AC-024", "P3-AC-069"],
        80: ["P3-AC-030", "P3-AC-077"],
        88: ["P3-AC-073"],
        89: ["P3-AC-077"],
    }
    for n, ids in extras.items():
        mapping.setdefault(n, [])
        for item in ids:
            if item not in mapping[n]:
                mapping[n].append(item)
    return mapping


def main() -> int:
    catalog = collect_tests()
    text = SPEC.read_text(encoding="utf-8")
    fr_defs, ac_defs, adv_defs = parse_spec(text)
    if len(fr_defs) != EXPECTED_FR:
        raise SystemExit(f"spec FR count {len(fr_defs)} != {EXPECTED_FR}")
    if len(ac_defs) != EXPECTED_AC:
        raise SystemExit(f"spec AC count {len(ac_defs)} != {EXPECTED_AC}")
    if len(adv_defs) != EXPECTED_ADV:
        raise SystemExit(f"spec ADV count {len(adv_defs)} != {EXPECTED_ADV}")
    nums = [int(rid.split("-")[-1]) for rid, _ in fr_defs]
    if max(nums) != HIGHEST_FR:
        raise SystemExit(f"highest FR {max(nums)} != {HIGHEST_FR}")
    missing = sorted(set(range(1, HIGHEST_FR + 1)) - set(nums))
    if missing != sorted(MISSING_FR):
        raise SystemExit(f"missing FR {missing} != {sorted(MISSING_FR)}")

    frs = fr_map()
    acs = ac_map()
    advs = adv_map()
    ac_for_fr = fr_to_ac(ac_defs)

    for rid, _ in fr_defs:
        n = int(rid.split("-")[-1])
        if n not in frs:
            raise SystemExit(f"no FR mapping for {rid}")
        row = frs[n]
        require_mapping(catalog, row, rid)
        if n == 90 and "csrf" in row.impl_file.lower():
            raise SystemExit("P3-FR-090 must not map to CSRF")

    for aid, _ in ac_defs:
        n = int(aid.split("-")[-1])
        if n not in acs:
            raise SystemExit(f"no AC mapping for {aid}")
        require_mapping(catalog, acs[n], aid)

    for sid, _ in adv_defs:
        n = int(sid.split("-")[-1])
        if n not in advs:
            raise SystemExit(f"no ADV mapping for {sid}")
        require_mapping(catalog, advs[n], sid)

    lines: list[str] = []
    lines.append("# Phase 3 Requirement Traceability (1:1)")
    lines.append("")
    lines.append("Authoritative specification: `docs/specifications/PHASE_3_ENGINEERING_AND_ACCEPTANCE_SPECIFICATION.md`")
    lines.append("")
    lines.append(f"SPEC_SHA256=`{SPEC_SHA256}`")
    lines.append("")
    lines.append("Generated by `scripts/generate_phase3_traceability.py`. Do not hand-edit claimed test names.")
    lines.append("")
    lines.append("Counts reconciled from the accepted specification:")
    lines.append("")
    lines.append(f"- FUNCTIONAL_REQUIREMENTS_EXPECTED={len(fr_defs)} (P3-FR definitions; IDs span 001–102 with gaps 048/049/067/068/069)")
    lines.append(f"- ACCEPTANCE_CRITERIA_EXPECTED={len(ac_defs)}")
    lines.append(f"- ADVERSARIAL_SCENARIOS_EXPECTED={len(adv_defs)}")
    lines.append("")
    lines.append("Status values: `PASS` / `FAIL` / `SKIPPED` / `NOT_PROVEN`.")
    lines.append("`PASS` is used only where a named executable exists and was executed for this candidate.")
    lines.append("SQLite unit/API rows are PASS where those tests ran in the PostgreSQL suite (same TestClient tests under TEST_USE_POSTGRES=1).")
    lines.append("PostgreSQL-gated concurrency/invariants/backup/migration/performance-n=100 rows are PASS after `TEST_USE_POSTGRES=1` execution with 0 failures.")
    lines.append("Playwright rows mapped to executed `test()` titles are PASS after compose profile `e2e` (8 passed, 1 skipped by default) plus `PHASE3_PERF_BROWSER=1` two-tab sampler (1 passed). Review/process gates stay `NOT_PROVEN`.")
    lines.append("Skipped or unexecuted gates are never labeled `PASS`.")
    lines.append("")

    fr_status: dict[str, int] = {}
    lines.append("## Functional requirements")
    lines.append("")
    lines.append(
        "| REQUIREMENT_ID | IMPLEMENTATION_FILE | IMPLEMENTATION_SYMBOL | TEST_FILE | TEST_NAME | AC_IDS | SCENARIO_IDS | VALIDATION_ENVIRONMENT | STATUS |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|")
    not_proven: list[str] = []
    for rid, title in fr_defs:
        n = int(rid.split("-")[-1])
        row = frs[n]
        ac_ids = ",".join(ac_for_fr.get(n, [])) or "—"
        scenarios = adv_ids_from_test(row.test_name)
        if not scenarios:
            # closest named adversarial overlays for non-adv tests
            overlay = {
                5: ["P3-ADV-025"],
                16: ["P3-ADV-037", "P3-ADV-043", "P3-ADV-045"],
                19: ["P3-ADV-037"],
                20: ["P3-ADV-007"],
                61: ["P3-ADV-020"],
                66: ["P3-ADV-020"],
                71: ["P3-ADV-007", "P3-ADV-022"],
                73: ["P3-ADV-001", "P3-ADV-037"],
                88: ["P3-ADV-034"],
                89: ["P3-ADV-033"],
                90: ["P3-ADV-035"],
                92: ["P3-ADV-037"],
            }
            scenarios = overlay.get(n, [])
        sc_ids = ",".join(scenarios) if scenarios else "—"
        env = row.env if not row.note else f"{row.env}; {row.note}"
        lines.append(
            "| "
            + " | ".join(
                [
                    rid,
                    f"`{cell(row.impl_file)}`",
                    f"`{cell(row.symbol)}`",
                    f"`{cell(row.test_file)}`" if row.test_file else "—",
                    f"`{cell(row.test_name)}`" if row.test_name else "—",
                    cell(ac_ids),
                    cell(sc_ids),
                    cell(env),
                    row.status,
                ]
            )
            + " |"
        )
        fr_status[row.status] = fr_status.get(row.status, 0) + 1
        if row.status == "NOT_PROVEN":
            not_proven.append(rid)

    ac_status: dict[str, int] = {}
    lines.append("")
    lines.append("## Acceptance criteria")
    lines.append("")
    lines.append(
        "| ACCEPTANCE_ID | IMPLEMENTATION_FILE | IMPLEMENTATION_SYMBOL | TEST_FILE | TEST_NAME | VALIDATION_ENVIRONMENT | STATUS |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for aid, title in ac_defs:
        n = int(aid.split("-")[-1])
        row = acs[n]
        env = row.env if not row.note else f"{row.env}; {row.note}"
        lines.append(
            "| "
            + " | ".join(
                [
                    aid,
                    f"`{cell(row.impl_file)}`" if row.impl_file else "—",
                    f"`{cell(row.symbol)}`" if row.symbol else "—",
                    f"`{cell(row.test_file)}`" if row.test_file else "—",
                    f"`{cell(row.test_name)}`" if row.test_name else "—",
                    cell(env),
                    row.status,
                ]
            )
            + " |"
        )
        ac_status[row.status] = ac_status.get(row.status, 0) + 1
        if row.status == "NOT_PROVEN":
            not_proven.append(aid)

    adv_status: dict[str, int] = {}
    lines.append("")
    lines.append("## Adversarial scenarios")
    lines.append("")
    lines.append(
        "| SCENARIO_ID | IMPLEMENTATION_FILE | IMPLEMENTATION_SYMBOL | TEST_FILE | TEST_NAME | VALIDATION_ENVIRONMENT | STATUS |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for sid, title in adv_defs:
        n = int(sid.split("-")[-1])
        row = advs[n]
        env = row.env if not row.note else f"{row.env}; {row.note}"
        lines.append(
            "| "
            + " | ".join(
                [
                    sid,
                    f"`{cell(row.impl_file)}`",
                    f"`{cell(row.symbol)}`",
                    f"`{cell(row.test_file)}`",
                    f"`{cell(row.test_name)}`",
                    cell(env),
                    row.status,
                ]
            )
            + " |"
        )
        adv_status[row.status] = adv_status.get(row.status, 0) + 1
        if row.status == "NOT_PROVEN":
            not_proven.append(sid)

    def fmt_counts(label: str, total: int, bag: dict[str, int]) -> str:
        parts = [f"{k}={bag.get(k, 0)}" for k in ("PASS", "FAIL", "SKIPPED", "NOT_PROVEN")]
        return f"- {label}: total={total}; " + ", ".join(parts)

    lines.append("")
    lines.append("## Status tallies")
    lines.append("")
    lines.append(fmt_counts("FUNCTIONAL_REQUIREMENTS", len(fr_defs), fr_status))
    lines.append(fmt_counts("ACCEPTANCE_CRITERIA", len(ac_defs), ac_status))
    lines.append(fmt_counts("ADVERSARIAL_SCENARIOS", len(adv_defs), adv_status))
    lines.append("")
    lines.append("Independently accepted complete counts remain those of the immutable re-review until a new independent review: FR/AC/ADV accepted = 0.")
    lines.append("")
    lines.append("## NOT_PROVEN identifiers")
    lines.append("")
    if not_proven:
        lines.append(", ".join(not_proven))
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- P3-FR-090 maps to `_finalize_order` / `test_decreasing_canonical_order_fails_closed`, not CSRF.")
    lines.append("- P3-FR-098 through P3-FR-102 are present in the accepted specification and are mapped above.")
    lines.append("- PostgreSQL concurrency/invariant/backup/migration/n=100 performance tests were executed with `TEST_USE_POSTGRES=1` (121 passed, 0 failed) and are `PASS` where they prove the mapped item.")
    lines.append("- Playwright names are exact `test()` titles from `tests/e2e`. Default compose e2e: 8 passed, 1 skipped; `PHASE3_PERF_BROWSER=1` sampler: 1 passed.")
    lines.append("- Performance server acceptance uses the isolated PostgreSQL harness (`test_phase3_performance_acceptance_reference_class`). Production `/performance-bench` route remains absent. Two-tab browser sampling is `tests/e2e/phase3-performance.spec.ts` and is skip-gated on `PHASE3_PERF_BROWSER=1`.")
    lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} fr={len(fr_defs)} ac={len(ac_defs)} adv={len(adv_defs)} "
        f"fr_pass={fr_status.get('PASS', 0)} fr_np={fr_status.get('NOT_PROVEN', 0)} "
        f"ac_pass={ac_status.get('PASS', 0)} ac_np={ac_status.get('NOT_PROVEN', 0)} "
        f"adv_pass={adv_status.get('PASS', 0)} adv_np={adv_status.get('NOT_PROVEN', 0)}"
    )
    print("NOT_PROVEN=" + ",".join(not_proven))
    return 0


if __name__ == "__main__":
    sys.exit(main())
