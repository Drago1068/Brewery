"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import {
  FermentationDetails,
  activeFermentationStage,
  conditioningRequired,
  dueReminders,
  fermentationCommand,
  measurementCommand,
} from "@/lib/fermentation";
import { newOperationId } from "@/lib/brew";

export default function FermentationWorksheetPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [session, setSession] = useState<FermentationDetails>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [gravityValue, setGravityValue] = useState("");
  const [tempValue, setTempValue] = useState("");
  const [note, setNote] = useState("");
  const [overrideComplete, setOverrideComplete] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideReadiness, setOverrideReadiness] = useState(false);
  const [readinessOverrideReason, setReadinessOverrideReason] = useState("");
  const [abortReason, setAbortReason] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const details = await apiFetch<FermentationDetails>(`/fermentation-sessions/${id}`);
      setSession(details);
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) router.replace("/login");
      else if (reason instanceof ApiError && reason.status === 404) {
        setError("Fermentation session not found.");
        setSession(undefined);
      } else {
        setError(reason instanceof ApiError ? reason.message : "Could not load fermentation state.");
      }
    }
  }, [id, router]);

  useEffect(() => {
    const initial = window.setTimeout(refresh, 0);
    const sync = window.setInterval(refresh, 15000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(sync);
    };
  }, [refresh]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  async function mutate(path: string, body?: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      const latest = await apiFetch<FermentationDetails>(`/fermentation-sessions/${id}`);
      setSession(latest);
      await apiFetch(path, {
        method: "POST",
        body: JSON.stringify(fermentationCommand(latest.revision, body)),
      });
      await refresh();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setError(`${reason.message} Refreshing authoritative state…`);
        await refresh();
      } else {
        setError(reason instanceof ApiError ? reason.message : "Action failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function recordMeasurement(
    event: FormEvent<HTMLFormElement>,
    measurementType: "FERMENTATION_GRAVITY" | "CONDITIONING_TEMPERATURE",
  ) {
    event.preventDefault();
    if (!session) return;
    const stage = activeFermentationStage(session);
    if (!stage) {
      setError("No active fermentation/conditioning stage is available for measurements.");
      return;
    }
    const value = measurementType === "FERMENTATION_GRAVITY" ? gravityValue : tempValue;
    if (!value) {
      setError("Measurement value is required.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const latest = await apiFetch<FermentationDetails>(`/fermentation-sessions/${id}`);
      setSession(latest);
      const targetStage = activeFermentationStage(latest) ?? stage;
      await apiFetch(`/fermentation-sessions/${id}/measurements`, {
        method: "POST",
        body: JSON.stringify(
          measurementCommand({
            measurement_type: measurementType,
            value,
            unit: measurementType === "FERMENTATION_GRAVITY" ? "SG" : "C",
            observed_at: new Date().toISOString(),
            stage_instance_id: targetStage.id,
            method: measurementType === "FERMENTATION_GRAVITY" ? "HYDROMETER" : "PROBE",
            sample_temperature_c:
              measurementType === "FERMENTATION_GRAVITY" ? "20.00" : undefined,
            note: note || null,
            expected_revision: latest.revision,
          }),
        ),
      });
      setGravityValue("");
      setTempValue("");
      setNote("");
      await refresh();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setError(`${reason.message} Refreshing authoritative state…`);
        await refresh();
      } else {
        setError(reason instanceof ApiError ? reason.message : "Measurement failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function acknowledgeReminder(reminderId: string) {
    setBusy(true);
    setError("");
    try {
      const latest = await apiFetch<FermentationDetails>(`/fermentation-sessions/${id}`);
      setSession(latest);
      await apiFetch(`/fermentation-sessions/reminders/${reminderId}/acknowledge`, {
        method: "POST",
        body: JSON.stringify({
          operation_id: newOperationId(),
          expected_revision: latest.revision,
        }),
      });
      await refresh();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setError(`${reason.message} Refreshing authoritative state…`);
        await refresh();
      } else {
        setError(reason instanceof ApiError ? reason.message : "Acknowledge failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!session && !error) {
    return (
      <div className="loading" aria-live="polite">
        Restoring authoritative fermentation state…
      </div>
    );
  }

  if (!session) {
    return (
      <div className="brew-shell">
        <div className="alert error" role="alert" id="ferment-session-error" tabIndex={-1}>
          {error || "Fermentation session unavailable."}
        </div>
        <Link href="/">Return to recipes</Link>
      </div>
    );
  }

  const due = dueReminders(session);
  const handoff = session.packaging_readiness_handoff;
  const readiness = session.packaging_readiness_assessment;
  const needsConditioning = conditioningRequired(session);
  const canCompleteFermentation = session.status === "ACTIVE";
  const canStartConditioning = session.status === "FERMENTATION_COMPLETE" && needsConditioning;
  const canSkipConditioning = session.status === "FERMENTATION_COMPLETE" && !needsConditioning;
  const canCompleteConditioning = session.status === "CONDITIONING";
  const canAssess =
    session.status === "CONDITIONING_COMPLETE" ||
    session.status === "COMPLETION_ASSESSED" ||
    session.status === "CLOSED";
  const canHandoff =
    Boolean(readiness?.id) &&
    (session.status === "COMPLETION_ASSESSED" ||
      session.status === "CONDITIONING_COMPLETE" ||
      session.status === "CLOSED");
  const canClose = session.status === "HANDOFF_READY";
  const terminal = session.status === "CLOSED" || session.status === "ABORTED";

  return (
    <div className="brew-shell ferment-shell" data-testid="ferment-worksheet" data-busy={busy ? "true" : "false"}>
      <section className="brew-topbar">
        <div>
          <div className="eyebrow">Fermentation worksheet</div>
          <h1>Fermentation</h1>
          <p>
            Session {session.id.slice(0, 8)} · brew {session.brew_session_id.slice(0, 8)} · rev{" "}
            {session.revision}
            {session.plan_kind ? ` · plan ${session.plan_kind}` : ""}
          </p>
          <p>
            <Link href={`/brew/${session.brew_session_id}`}>Open source brew day</Link>
          </p>
        </div>
        <span
          className={`status ${session.status.toLowerCase()}`}
          role="status"
          aria-label="Session status"
          data-testid="ferment-status"
        >
          {session.status}
        </span>
      </section>

      {error && (
        <div
          className="alert error"
          role="alert"
          id="ferment-session-error"
          ref={errorRef}
          tabIndex={-1}
        >
          {error}
        </div>
      )}

      <section className="card" aria-label="Lifecycle stages">
        <h2>Lifecycle stages</h2>
        <ol className="timer-list" data-testid="ferment-stages">
          {session.stages.map((stage) => (
            <li key={stage.id}>
              <strong>{stage.canonical_stage_type}</strong>
              <span>{stage.status}</span>
              <span>#{stage.occurrence_number}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="now-panel" aria-label="Authoritative derived state">
        <div className="eyebrow">Derived state</div>
        <strong data-testid="stable-gravity">
          Stable gravity: {session.derived_gravity?.stable_gravity_status ?? "UNKNOWN"}
        </strong>
        <small>
          FG {session.derived_gravity?.final_gravity_sg ?? "—"} · ABV{" "}
          {session.derived_gravity?.abv_percent ?? "—"}% · server projection only
        </small>
      </section>

      {due.length > 0 && (
        <section className="card" aria-label="Required actions" aria-live="polite">
          <h2>Reminders</h2>
          <ul className="timer-list" data-testid="ferment-reminders">
            {due.map((reminder) => (
              <li key={reminder.id}>
                <div>
                  <strong>{reminder.message || reminder.reminder_type || "Reminder"}</strong>
                  <small>
                    {reminder.status}
                    {reminder.due_at ? ` · due ${reminder.due_at}` : ""}
                  </small>
                </div>
                <button
                  type="button"
                  className="primary"
                  disabled={busy || terminal}
                  onClick={() => acknowledgeReminder(reminder.id)}
                >
                  Acknowledge
                </button>
              </li>
            ))}
          </ul>
          <p className="lede" style={{ marginBottom: 0, fontSize: "0.9rem" }}>
            Acknowledgement is not requirement satisfaction.
          </p>
        </section>
      )}

      {!terminal && (
        <section className="card" aria-label="Record measurement">
          <h2>Measurements</h2>
          <form
            className="measurement-form"
            onSubmit={(event) => recordMeasurement(event, "FERMENTATION_GRAVITY")}
            aria-describedby={error ? "ferment-session-error" : undefined}
          >
            <label>
              Gravity (SG)
              <input
                name="gravity"
                inputMode="decimal"
                value={gravityValue}
                onChange={(event) => setGravityValue(event.target.value)}
                aria-label="Gravity reading"
              />
            </label>
            <label className="full">
              Measurement note
              <input
                name="note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                maxLength={4000}
                aria-label="Measurement note"
              />
            </label>
            <button className="primary full" disabled={busy || !gravityValue} type="submit">
              Record gravity
            </button>
          </form>
          {session.status === "CONDITIONING" && (
            <form
              className="measurement-form"
              style={{ marginTop: 16 }}
              onSubmit={(event) => recordMeasurement(event, "CONDITIONING_TEMPERATURE")}
              aria-describedby={error ? "ferment-session-error" : undefined}
            >
              <label>
                Conditioning temperature (°C)
                <input
                  name="temperature"
                  inputMode="decimal"
                  value={tempValue}
                  onChange={(event) => setTempValue(event.target.value)}
                  aria-label="Conditioning temperature"
                />
              </label>
              <button className="primary full" disabled={busy || !tempValue} type="submit">
                Record temperature
              </button>
            </form>
          )}
          <ul className="note-list" aria-label="Recorded measurements">
            {session.measurements.slice(-8).map((item) => (
              <li key={item.id}>
                {item.measurement_type}: {item.canonical_value} {item.canonical_unit}
                {item.note ? ` · ${item.note}` : ""}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card" aria-label="Lifecycle commands">
        <h2>Lifecycle</h2>
        <div className="brew-toolbar">
          {session.status === "ACTIVE" && (
            <button
              type="button"
              className="secondary dark"
              disabled={busy}
              onClick={() => mutate(`/fermentation-sessions/${id}/commands/pause`)}
            >
              Pause session
            </button>
          )}
          {session.status === "PAUSED" && (
            <button
              type="button"
              className="primary"
              disabled={busy}
              onClick={() => mutate(`/fermentation-sessions/${id}/commands/resume`)}
            >
              Resume session
            </button>
          )}
          {canCompleteFermentation && (
            <>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="checkbox"
                  checked={overrideComplete}
                  onChange={(event) => setOverrideComplete(event.target.checked)}
                  aria-label="Override fermentation completion eligibility"
                />
                Override eligibility
              </label>
              {overrideComplete && (
                <label className="full" style={{ flex: "1 1 100%" }}>
                  Override reason
                  <input
                    value={overrideReason}
                    onChange={(event) => setOverrideReason(event.target.value)}
                    aria-label="Override reason"
                    minLength={10}
                  />
                </label>
              )}
              <button
                type="button"
                className="primary"
                disabled={busy || (overrideComplete && overrideReason.trim().length < 10)}
                data-testid="complete-fermentation"
                onClick={() =>
                  mutate(`/fermentation-sessions/${id}/commands/complete-fermentation`, {
                    override: overrideComplete,
                    override_reason: overrideComplete ? overrideReason.trim() : undefined,
                  })
                }
              >
                Complete fermentation
              </button>
            </>
          )}
          {canStartConditioning && (
            <button
              type="button"
              className="primary"
              disabled={busy}
              data-testid="start-conditioning"
              onClick={() => mutate(`/fermentation-sessions/${id}/commands/start-conditioning`)}
            >
              Start conditioning
            </button>
          )}
          {canSkipConditioning && (
            <button
              type="button"
              className="primary"
              disabled={busy}
              data-testid="skip-conditioning"
              onClick={() => mutate(`/fermentation-sessions/${id}/commands/skip-conditioning`)}
            >
              Skip conditioning
            </button>
          )}
          {canCompleteConditioning && (
            <button
              type="button"
              className="primary"
              disabled={busy}
              data-testid="complete-conditioning"
              onClick={() =>
                mutate(`/fermentation-sessions/${id}/commands/complete-conditioning`, {
                  override: true,
                  override_reason: "Worksheet completion override for operable conditioning close",
                })
              }
            >
              Complete conditioning
            </button>
          )}
          {canAssess && (
            <>
              <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  type="checkbox"
                  checked={overrideReadiness}
                  onChange={(event) => setOverrideReadiness(event.target.checked)}
                  aria-label="Override packaging readiness R3"
                />
                Override OG readiness (R3)
              </label>
              {overrideReadiness && (
                <label className="full" style={{ flex: "1 1 100%" }}>
                  Readiness override reason
                  <input
                    value={readinessOverrideReason}
                    onChange={(event) => setReadinessOverrideReason(event.target.value)}
                    aria-label="Readiness override reason"
                    minLength={10}
                  />
                </label>
              )}
              <button
                type="button"
                className="primary"
                disabled={
                  busy || (overrideReadiness && readinessOverrideReason.trim().length < 10)
                }
                data-testid="assess-readiness"
                onClick={() =>
                  mutate(`/fermentation-sessions/${id}/commands/assess-packaging-readiness`, {
                    override: overrideReadiness,
                    override_reason: overrideReadiness
                      ? readinessOverrideReason.trim()
                      : undefined,
                  })
                }
              >
                Assess packaging readiness
              </button>
            </>
          )}
          {canHandoff && readiness?.id && (
            <button
              type="button"
              className="primary"
              disabled={busy}
              data-testid="record-handoff"
              onClick={() =>
                mutate(`/fermentation-sessions/${id}/commands/record-packaging-readiness-handoff`, {
                  assessment_id: readiness.id,
                })
              }
            >
              Record packaging readiness handoff
            </button>
          )}
          {canClose && (
            <button
              type="button"
              className="primary"
              disabled={busy}
              data-testid="close-fermentation"
              onClick={() => mutate(`/fermentation-sessions/${id}/commands/close`)}
            >
              Close fermentation session
            </button>
          )}
        </div>
        {!terminal && (
          <div style={{ marginTop: 16 }}>
            <label>
              Abort reason
              <input
                value={abortReason}
                onChange={(event) => setAbortReason(event.target.value)}
                aria-label="Abort reason"
              />
            </label>
            <button
              type="button"
              className="secondary dark"
              disabled={busy || abortReason.trim().length < 10}
              onClick={() =>
                mutate(`/fermentation-sessions/${id}/commands/abort`, {
                  reason: abortReason.trim(),
                })
              }
            >
              Abort session
            </button>
          </div>
        )}
      </section>

      <section className="card" aria-label="Readiness and handoff">
        <h2>Packaging readiness</h2>
        <dl className="performance" data-testid="readiness-panel">
          <div>
            <dt>Assessment outcome</dt>
            <dd>{readiness?.outcome ?? "None"}</dd>
          </div>
          <div>
            <dt>Assessment id</dt>
            <dd data-testid="assessment-id">{readiness?.id ?? "—"}</dd>
          </div>
          <div>
            <dt>Handoff status</dt>
            <dd data-testid="handoff-status">
              {handoff
                ? `${handoff.readiness_status} v${handoff.handoff_version}${
                    handoff.is_current ? " (current)" : ""
                  }${handoff.invalidated_at ? " INVALIDATED" : ""}`
                : "None"}
            </dd>
          </div>
          <div>
            <dt>Handoff id</dt>
            <dd data-testid="handoff-id">{handoff?.id ?? "—"}</dd>
          </div>
        </dl>
        <p className="lede" style={{ fontSize: "0.9rem", marginBottom: 0 }}>
          Readiness and handoff are Phase 4 facts only. No packaging execution is available here.
        </p>
      </section>

      {(session.waivers.length > 0 || (session.deviations?.length ?? 0) > 0) && (
        <section className="card" aria-label="Waivers and deviations">
          <h2>Waivers &amp; deviations</h2>
          <ul className="note-list">
            {session.waivers.map((item) => (
              <li key={item.id}>
                Waiver {item.requirement_class ?? item.id.slice(0, 8)} · {item.status}: {item.reason}
              </li>
            ))}
            {(session.deviations ?? []).map((item) => (
              <li key={item.id}>
                Deviation {item.kind ?? item.id.slice(0, 8)} · {item.status ?? "OPEN"}
              </li>
            ))}
          </ul>
        </section>
      )}

      {session.timers.length > 0 && (
        <section className="card" aria-label="Timers">
          <h2>Timers</h2>
          <ul className="timer-list" aria-label="Active timers">
            {session.timers.map((timer) => (
              <li key={timer.id}>
                <strong>{timer.name}</strong>
                <span
                  role="timer"
                  aria-label={`${timer.name} status`}
                  data-testid={`timer-${timer.id}`}
                >
                  {timer.status}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
