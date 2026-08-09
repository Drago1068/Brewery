import { apiFetch } from "./http";
import type {
  BrewDayReport,
  BrewPlan,
  BrewSession,
  BrewTimer,
  MeasurementRequirement,
} from "./types";

export async function createBrewPlan(
  recipeVersionId: string,
  body: {
    client_submission_id: string;
    readiness_acknowledgement?: {
      acknowledged: boolean;
      note?: string;
      actor_id?: string;
    } | null;
  },
): Promise<BrewPlan> {
  return apiFetch(`/api/v1/recipe-versions/${recipeVersionId}/brew-plans`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function createBrewSession(
  planId: string,
  body: { client_submission_id: string; client_context?: string },
): Promise<BrewSession> {
  return apiFetch(`/api/v1/brew-plans/${planId}/sessions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getBrewSession(sessionId: string): Promise<BrewSession> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}`);
}

export async function applyTransition(
  sessionId: string,
  body: {
    client_submission_id: string;
    expected_session_version: number;
    command: string;
    skip_reason?: string;
    abort_reason?: string;
    client_occurred_at?: string;
  },
): Promise<BrewSession> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}/transitions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listRequirements(
  sessionId: string,
): Promise<MeasurementRequirement[]> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}/requirements`);
}

export async function captureMeasurement(
  sessionId: string,
  body: Record<string, unknown>,
): Promise<{ record: unknown; session_version: number; requirement?: unknown }> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}/measurements`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function missRequirement(
  requirementId: string,
  body: Record<string, unknown>,
): Promise<{ requirement: MeasurementRequirement; session_version: number }> {
  return apiFetch(`/api/v1/measurement-requirements/${requirementId}/miss`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function waiveRequirement(
  requirementId: string,
  body: Record<string, unknown>,
): Promise<{ requirement: MeasurementRequirement; session_version: number }> {
  return apiFetch(`/api/v1/measurement-requirements/${requirementId}/waive`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function instrumentCorrection(
  recordId: string,
  body: Record<string, unknown>,
): Promise<{ record: unknown; session_version: number }> {
  return apiFetch(`/api/v1/measurement-records/${recordId}/instrument-corrections`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function userRevision(
  recordId: string,
  body: Record<string, unknown>,
): Promise<{ record: unknown; session_version: number }> {
  return apiFetch(`/api/v1/measurement-records/${recordId}/revisions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listTimers(
  sessionId: string,
): Promise<{ brew_session_id: string; timers: BrewTimer[] }> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}/timers`);
}

export async function startTimer(
  sessionId: string,
  body: Record<string, unknown>,
): Promise<{ timer: BrewTimer; session_version: number }> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}/timers`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function stopTimer(
  timerId: string,
  body: Record<string, unknown>,
): Promise<{ timer: BrewTimer; session_version: number }> {
  return apiFetch(`/api/v1/timers/${timerId}/stop`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function cancelTimer(
  timerId: string,
  body: Record<string, unknown>,
): Promise<{ timer: BrewTimer; session_version: number }> {
  return apiFetch(`/api/v1/timers/${timerId}/cancel`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function observeElapsed(
  timerId: string,
  body: Record<string, unknown>,
): Promise<{ timer: BrewTimer; session_version: number }> {
  return apiFetch(`/api/v1/timers/${timerId}/observe-elapsed`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getBrewDayReport(sessionId: string): Promise<BrewDayReport> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}/report`);
}

export async function createFermentationHandoff(
  sessionId: string,
  body: { client_submission_id: string; expected_session_version: number },
): Promise<{
  handoff: Record<string, unknown>;
  session_status: string;
  session_version: number;
}> {
  return apiFetch(`/api/v1/brew-sessions/${sessionId}/fermentation-handoff`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getBrewPlan(planId: string): Promise<BrewPlan> {
  // Plans are returned from create; for refresh we load via session's plan by listing
  // through a lightweight approach — use session and reconstruct from report when needed.
  // Backend has no GET plan route in E2A; callers should keep plan in local storage.
  return apiFetch(`/api/v1/brew-plans/${planId}`);
}
