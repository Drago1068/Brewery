export type SyncStatus = "SYNCED" | "UNSYNCED" | "SYNCING" | "SYNC_FAILED" | "REJECTED" | "CONFLICT";

export type BrewSession = {
  id: string;
  brew_plan_id: string;
  brewery_id: string;
  status: string;
  current_stage_code: string | null;
  version: number;
  started_at: string | null;
  closed_at: string | null;
  abort_reason: string | null;
  created_by: string;
  created_at: string;
  stage_occurrences: StageOccurrence[];
};

export type StageOccurrence = {
  id: string;
  stage_code: string;
  sequence_no: number;
  status: string;
  entered_at: string | null;
  exited_at: string | null;
  skip_reason: string | null;
};

export type MeasurementRequirement = {
  id: string;
  brew_session_id: string;
  stage_occurrence_id: string | null;
  measurement_definition_id: string;
  measurement_code: string;
  requirement_level: string;
  planned_value: string | null;
  planned_unit: string | null;
  planned_kind: string | null;
  validation_min: string | null;
  validation_max: string | null;
  status: string;
  created_at: string | null;
  record: MeasurementRecord | null;
};

export type MeasurementRecord = {
  id: string;
  requirement_id: string;
  brew_session_id: string;
  raw_value: string | null;
  raw_unit: string | null;
  corrected_value: string | null;
  corrected_unit: string | null;
  display_value: string | null;
  display_unit: string | null;
  value_kind: string;
  confidence: string | null;
  instrument: string | null;
  method: string | null;
  provenance: Record<string, unknown> | null;
  validation_class: string | null;
  validation_notes: string | null;
  latest_observation_history_id: string | null;
  first_captured_at: string | null;
  captured_by: string | null;
  client_submission_id: string | null;
  updated_at: string | null;
};

export type BrewTimer = {
  id: string;
  brewery_id: string;
  brew_session_id: string;
  stage_occurrence_id: string | null;
  label: string;
  target_duration_seconds: number | null;
  started_at: string | null;
  client_started_at: string | null;
  ends_at: string | null;
  elapsed_at: string | null;
  stopped_at: string | null;
  cancelled_at: string | null;
  status: string;
  computed_past_due: boolean;
  start_client_submission_id: string;
  created_by: string;
  created_at: string | null;
};

export type BrewPlan = {
  id: string;
  brewery_id: string;
  recipe_id: string;
  recipe_version_id: string;
  status: string;
  batch_size: string;
  batch_size_unit: string;
  equipment_profile_id: string | null;
  equipment_snapshot: Record<string, unknown> | null;
  recipe_snapshot: Record<string, unknown>;
  planned_calculation_snapshot: Record<string, unknown>;
  readiness_status: string;
  readiness_summary: string;
  readiness_checks_snapshot: unknown[];
  readiness_acknowledged: boolean;
  readiness_acknowledged_at: string | null;
  readiness_acknowledged_by: string | null;
  readiness_acknowledgement_note: string | null;
  created_by: string;
  created_at: string;
};

export type BrewDayReport = {
  brew_session_id: string;
  generated_at: string | null;
  session_summary: Record<string, unknown>;
  data_completeness: Record<string, unknown>;
  process_adherence: Record<string, unknown>;
  planned_vs_actual: Array<Record<string, unknown>>;
  measurement_quality: Array<Record<string, unknown>>;
  timer_evidence: Array<Record<string, unknown>>;
  deviations_and_warnings: Array<Record<string, unknown>>;
  readiness_acknowledgement: Record<string, unknown>;
  overall_brew_score: null;
  dimensions_are_independent: boolean;
  event_count: number;
};

export type ApiErrorBody = {
  code?: string;
  message?: string;
  pending_codes?: string[];
  [key: string]: unknown;
};
