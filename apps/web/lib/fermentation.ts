import { newOperationId } from "./brew";

export type FermentationStage = {
  id: string;
  canonical_stage_type: string;
  occurrence_number: number;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  activation_ordinal?: number;
};

export type FermentationMeasurement = {
  id: string;
  measurement_type: string;
  raw_value: string;
  raw_unit: string;
  canonical_value: string;
  canonical_unit: string;
  observed_at: string;
  method?: string | null;
  note?: string | null;
  stage_instance_id: string;
  late_entry?: boolean;
};

export type FermentationReminder = {
  id: string;
  reminder_type?: string;
  message?: string;
  status: string;
  due_at?: string | null;
  requirement_class?: string | null;
};

export type FermentationTimer = {
  id: string;
  name: string;
  status: string;
  planned_duration_seconds: number;
  elapsed_seconds?: number;
  deadline_at?: string | null;
};

export type FermentationAssessment = {
  id: string;
  assessment_kind?: string;
  outcome: string;
  is_current?: boolean;
  predicate_results?: Record<string, unknown>;
  assessed_at?: string;
  override_reason?: string | null;
};

export type FermentationHandoff = {
  id: string;
  handoff_version: number;
  is_current: boolean;
  readiness_status: string;
  assessed_at?: string;
  assessment_id?: string;
  invalidated_at?: string | null;
} | null;

export type FermentationWaiver = {
  id: string;
  requirement_class?: string;
  status: string;
  reason: string;
};

export type FermentationSessionSummary = {
  id: string;
  brew_session_id: string;
  status: string;
  revision: number;
  started_at?: string | null;
  closed_at?: string | null;
  aborted_at?: string | null;
  handoff_ready_at?: string | null;
};

export type FermentationDetails = {
  id: string;
  brew_session_id: string;
  status: string;
  revision: number;
  started_at?: string | null;
  closed_at?: string | null;
  aborted_at?: string | null;
  abort_reason?: string | null;
  conditioning_skipped?: boolean;
  conditioning_mode?: string | null;
  plan_kind?: string | null;
  stages: FermentationStage[];
  measurements: FermentationMeasurement[];
  reminders: FermentationReminder[];
  timers: FermentationTimer[];
  deviations?: Array<{ id: string; status?: string; kind?: string }>;
  waivers: FermentationWaiver[];
  completion_assessment?: FermentationAssessment | null;
  conditioning_assessment?: FermentationAssessment | null;
  packaging_readiness_assessment?: FermentationAssessment | null;
  packaging_readiness_handoff?: FermentationHandoff;
  derived_gravity?: {
    stable_gravity_status?: string;
    final_gravity_sg?: string | null;
    apparent_attenuation_ratio?: string | null;
    abv_percent?: string | null;
  } | null;
  og_consumption?: { status?: string; pinned_value?: string | null } | null;
  yeast_pitch_reference?: { yeast_note?: string | null } | null;
  plan_snapshot?: { payload?: { conditioning_required?: boolean } | null } | null;
};

export function fermentationCommand(
  revision: number | undefined,
  body?: Record<string, unknown>,
): Record<string, unknown> {
  return {
    operation_id: newOperationId(),
    expected_revision: revision ?? 0,
    ...body,
  };
}

export function measurementCommand(input: {
  measurement_type: string;
  value: string;
  unit: string;
  observed_at: string;
  stage_instance_id: string;
  method?: string;
  sample_temperature_c?: string;
  note?: string | null;
  expected_revision?: number;
}): Record<string, unknown> {
  return {
    operation_id: newOperationId(),
    measurement_type: input.measurement_type,
    value: input.value,
    unit: input.unit,
    observed_at: input.observed_at,
    stage_instance_id: input.stage_instance_id,
    source: "OBSERVED",
    method: input.method ?? "HYDROMETER",
    sample_temperature_c: input.sample_temperature_c ?? "20.00",
    note: input.note || null,
    expected_revision: input.expected_revision,
  };
}

export function activeFermentationStage(session: FermentationDetails): FermentationStage | undefined {
  return (
    session.stages.find(
      (stage) =>
        stage.canonical_stage_type === "ACTIVE_FERMENTATION" &&
        (stage.status === "ACTIVE" || stage.status === "PAUSED"),
    ) ??
    session.stages.find((stage) => stage.canonical_stage_type === "ACTIVE_FERMENTATION") ??
    session.stages.find(
      (stage) =>
        stage.canonical_stage_type === "CONDITIONING" &&
        (stage.status === "ACTIVE" || stage.status === "PAUSED"),
    )
  );
}

export function dueReminders(session: FermentationDetails): FermentationReminder[] {
  return session.reminders.filter((item) => item.status === "DUE" || item.status === "EXPIRED");
}

export function conditioningRequired(session: FermentationDetails): boolean {
  return Boolean(session.plan_snapshot?.payload?.conditioning_required);
}
