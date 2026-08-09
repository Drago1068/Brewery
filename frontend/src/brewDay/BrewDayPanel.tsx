import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import * as brewDayApi from "../api/brewDayApi";
import { ApiError } from "../api/http";
import type {
  BrewDayReport,
  BrewPlan,
  BrewSession,
  BrewTimer,
  MeasurementRequirement,
  SyncStatus,
} from "../api/types";
import { newClientSubmissionId } from "../lib/ids";
import {
  listQueuedMutations,
  overallSyncStatus,
} from "../offline/mutationQueue";
import { mutateWithQueue, replayPendingMutations } from "../offline/syncEngine";
import { STAGE_SEQUENCE, stageLabel, stagePurpose } from "./stageMeta";
import { formatDuration, reconstructTimerDisplay } from "./timerDisplay";

const SESSION_KEY = "brewingos.e2a6.activeBrewSessionId";
const PLAN_KEY = "brewingos.e2a6.activeBrewPlanId";

type Props = {
  breweryId: string;
  initialSessionId?: string | null;
  onError: (message: string | null) => void;
};

function confLabel(c: string | null | undefined): string {
  if (!c) return "";
  return c;
}

export default function BrewDayPanel({ breweryId, initialSessionId, onError }: Props) {
  const [session, setSession] = useState<BrewSession | null>(null);
  const [plan, setPlan] = useState<BrewPlan | null>(null);
  const [requirements, setRequirements] = useState<MeasurementRequirement[]>([]);
  const [timers, setTimers] = useState<BrewTimer[]>([]);
  const [report, setReport] = useState<BrewDayReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [syncStatus, setSyncStatus] = useState<SyncStatus>("SYNCED");
  const [now, setNow] = useState(Date.now());
  const [message, setMessage] = useState<string | null>(null);

  // Forms
  const [captureDraft, setCaptureDraft] = useState<Record<string, { value: string; unit: string; confidence: string; instrument: string }>>({});
  const [timerLabel, setTimerLabel] = useState("Rest timer");
  const [timerSeconds, setTimerSeconds] = useState("3600");
  const [skipReason, setSkipReason] = useState("");
  const [abortReason, setAbortReason] = useState("");
  const [waiveReason, setWaiveReason] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState<null | { kind: string; payload?: string }>(null);
  const [corrDraft, setCorrDraft] = useState<Record<string, { value: string; unit: string }>>({});
  const [revDraft, setRevDraft] = useState<Record<string, { value: string; unit: string; reason: string }>>({});

  const refreshSync = useCallback(() => {
    setSyncStatus(overallSyncStatus(listQueuedMutations()));
  }, []);

  const loadAll = useCallback(
    async (sessionId: string) => {
      const sess = await brewDayApi.getBrewSession(sessionId);
      setSession(sess);
      localStorage.setItem(SESSION_KEY, sess.id);
      localStorage.setItem(PLAN_KEY, sess.brew_plan_id);
      const [reqs, timerPayload, planRow] = await Promise.all([
        brewDayApi.listRequirements(sess.id),
        brewDayApi.listTimers(sess.id),
        brewDayApi.getBrewPlan(sess.brew_plan_id).catch(() => null),
      ]);
      setRequirements(reqs);
      setTimers(timerPayload.timers);
      if (planRow) setPlan(planRow);
      if (sess.current_stage_code === "BREW_DAY_AUDIT" || sess.status === "CLOSED" || sess.status === "HANDED_OFF" || sess.status === "ABORTED") {
        const r = await brewDayApi.getBrewDayReport(sess.id);
        setReport(r);
      } else {
        setReport(null);
      }
      refreshSync();
    },
    [refreshSync],
  );

  useEffect(() => {
    const id = initialSessionId || localStorage.getItem(SESSION_KEY);
    if (!id) return;
    void (async () => {
      try {
        await loadAll(id);
      } catch (e) {
        onError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [initialSessionId, loadAll, onError]);

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  useEffect(() => {
    const onOnline = () => {
      void (async () => {
        const result = await replayPendingMutations();
        refreshSync();
        if (session && (result.synced > 0 || result.conflicts > 0)) {
          await loadAll(session.id);
          if (result.conflicts > 0) {
            setMessage("Some offline actions need reconciliation — refresh showed server state. Conflicts were not blindly retried with a new submission ID.");
          }
        }
      })();
    };
    window.addEventListener("online", onOnline);
    return () => window.removeEventListener("online", onOnline);
  }, [session, loadAll, refreshSync]);

  const recipeName = useMemo(() => {
    const snap = plan?.recipe_snapshot as { name?: string; recipe?: { name?: string } } | undefined;
    return snap?.name || snap?.recipe?.name || "Brew Day";
  }, [plan]);

  const currentStage = useMemo(() => {
    if (!session?.current_stage_code) return null;
    return session.stage_occurrences.find((s) => s.stage_code === session.current_stage_code) ?? null;
  }, [session]);

  const stageReqs = useMemo(() => {
    if (!currentStage) return [];
    return requirements.filter((r) => r.stage_occurrence_id === currentStage.id);
  }, [requirements, currentStage]);

  const stageTimers = useMemo(() => {
    if (!currentStage) return timers;
    return timers.filter((t) => t.stage_occurrence_id === currentStage.id || !t.stage_occurrence_id);
  }, [timers, currentStage]);

  const elapsedDay = useMemo(() => {
    if (!session?.started_at) return null;
    const start = Date.parse(session.started_at);
    const end = session.closed_at ? Date.parse(session.closed_at) : now;
    return Math.max(0, Math.floor((end - start) / 1000));
  }, [session, now]);

  const pendingRequired = useMemo(
    () => requirements.filter((r) => r.requirement_level === "REQUIRED" && r.status === "PENDING"),
    [requirements],
  );

  const paused = session?.status === "PAUSED";
  const terminal = session && ["CLOSED", "ABORTED", "HANDED_OFF"].includes(session.status);
  const canAdvance = session?.status === "IN_PROGRESS" && !paused;

  async function runMutation<T>(
    operation: string,
    path: string,
    buildPayload: (id: string) => Record<string, unknown>,
    expectedVersion: number,
  ): Promise<T | null> {
    setBusy(true);
    onError(null);
    try {
      const result = await mutateWithQueue<T>({
        operation,
        path,
        buildPayload,
        expected_session_version: expectedVersion,
        session_id: session?.id ?? null,
      });
      refreshSync();
      if (result.ok) {
        await loadAll(session!.id);
        return result.data;
      }
      if ("queued" in result && result.queued && !("conflict" in result && result.conflict)) {
        setMessage(`Saved offline (${result.queued.status}). Will retry when online with the same submission ID.`);
        return null;
      }
      if ("conflict" in result && result.conflict) {
        await loadAll(session!.id);
        throw result.error;
      }
      return null;
    } catch (e) {
      onError(e instanceof ApiError ? `${e.code ?? "ERROR"}: ${e.message}` : e instanceof Error ? e.message : String(e));
      if (session) await loadAll(session.id).catch(() => undefined);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function startSession() {
    if (!session) return;
    await runMutation(
      "START_SESSION",
      `/api/v1/brew-sessions/${session.id}/transitions`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        command: "START_SESSION",
      }),
      session.version,
    );
  }

  async function advance() {
    if (!session || !canAdvance) return;
    const unresolved = stageReqs.filter((r) => r.status === "PENDING");
    if (unresolved.length > 0) {
      setMessage(
        `Unresolved measurements on this stage: ${unresolved.map((r) => r.measurement_code).join(", ")}. You can still advance if the backend allows; REQUIRED PENDING will block CLOSE.`,
      );
    }
    await runMutation(
      "ADVANCE_STAGE",
      `/api/v1/brew-sessions/${session.id}/transitions`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        command: "ADVANCE_STAGE",
      }),
      session.version,
    );
  }

  async function confirmSkip() {
    if (!session || !skipReason.trim()) return;
    setConfirm(null);
    await runMutation(
      "SKIP_STAGE",
      `/api/v1/brew-sessions/${session.id}/transitions`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        command: "SKIP_STAGE",
        skip_reason: skipReason.trim(),
      }),
      session.version,
    );
    setSkipReason("");
  }

  async function pauseResume(command: "PAUSE_SESSION" | "RESUME_SESSION") {
    if (!session) return;
    await runMutation(
      command,
      `/api/v1/brew-sessions/${session.id}/transitions`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        command,
      }),
      session.version,
    );
  }

  async function closeSession() {
    if (!session) return;
    if (pendingRequired.length > 0) {
      onError(
        `Cannot close: REQUIRED measurements still PENDING — ${pendingRequired.map((r) => r.measurement_code).join(", ")}. Capture, miss, or waive them first. Missing values are not filled automatically.`,
      );
      return;
    }
    await runMutation(
      "CLOSE_SESSION",
      `/api/v1/brew-sessions/${session.id}/transitions`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        command: "CLOSE_SESSION",
      }),
      session.version,
    );
    setMessage("Brew Day Closed. Fermentation handoff is not created automatically — use Continue to Fermentation when ready.");
  }

  async function abortSession() {
    if (!session || !abortReason.trim()) return;
    setConfirm(null);
    await runMutation(
      "ABORT_SESSION",
      `/api/v1/brew-sessions/${session.id}/transitions`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        command: "ABORT_SESSION",
        abort_reason: abortReason.trim(),
      }),
      session.version,
    );
    setMessage("Brew Day aborted. Evidence preserved. Fermentation handoff is not available.");
  }

  async function handoff() {
    if (!session || session.status !== "CLOSED") return;
    setConfirm(null);
    await runMutation(
      "CREATE_FERMENTATION_HANDOFF",
      `/api/v1/brew-sessions/${session.id}/fermentation-handoff`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
      }),
      session.version,
    );
    setMessage("HANDED_OFF — Epic 3 fermentation tracking begins next (not implemented in Epic 2A).");
  }

  async function capture(req: MeasurementRequirement) {
    if (!session) return;
    const draft = captureDraft[req.id] ?? {
      value: "",
      unit: req.planned_unit || "SG",
      confidence: "HIGH",
      instrument: "",
    };
    if (!draft.value.trim()) {
      onError("Enter a measurement value.");
      return;
    }
    setBusy(true);
    onError(null);
    try {
      const client_submission_id = newClientSubmissionId("CAPTURE");
      const result = await mutateWithQueue<{
        record: { validation_class?: string; validation_notes?: string | null; display_value?: string };
        session_version: number;
      }>({
        operation: "CAPTURE_MEASUREMENT",
        path: `/api/v1/brew-sessions/${session.id}/measurements`,
        expected_session_version: session.version,
        session_id: session.id,
        client_submission_id,
        buildPayload: (id) => ({
          client_submission_id: id,
          expected_session_version: session.version,
          requirement_id: req.id,
          raw_value: draft.value.trim(),
          raw_unit: draft.unit,
          confidence: draft.confidence,
          instrument: draft.instrument || null,
        }),
      });
      refreshSync();
      if (!result.ok) {
        if ("conflict" in result && result.conflict) throw result.error;
        setMessage("Measurement queued offline.");
        return;
      }
      const vc = result.data.record?.validation_class;
      if (vc === "UNUSUAL_VALUE" || vc === "DOMAIN_CONCERN") {
        setMessage(
          `${result.data.record.display_value} ${draft.unit} — ${vc === "UNUSUAL_VALUE" ? "Unusual compared with expected range" : "Domain concern"}. Value preserved as entered; not changed silently.`,
        );
      }
      await loadAll(session.id);
    } catch (e) {
      onError(e instanceof ApiError ? `${e.code ?? "ERROR"}: ${e.message}` : e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function missReq(req: MeasurementRequirement) {
    if (!session) return;
    setConfirm(null);
    await runMutation(
      "MISS_MEASUREMENT",
      `/api/v1/measurement-requirements/${req.id}/miss`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        reason: "Not captured during brew day",
      }),
      session.version,
    );
  }

  async function waiveReq(req: MeasurementRequirement) {
    if (!session) return;
    const reason = (waiveReason[req.id] || "").trim();
    if (!reason) {
      onError("Waive requires a reason.");
      return;
    }
    setConfirm(null);
    await runMutation(
      "WAIVE_MEASUREMENT",
      `/api/v1/measurement-requirements/${req.id}/waive`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        reason,
      }),
      session.version,
    );
  }

  async function startTimer() {
    if (!session || !canAdvance) return;
    const seconds = Number(timerSeconds);
    await runMutation(
      "START_TIMER",
      `/api/v1/brew-sessions/${session.id}/timers`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        label: timerLabel.trim() || "Timer",
        target_duration_seconds: Number.isFinite(seconds) && seconds > 0 ? seconds : null,
        stage_occurrence_id: currentStage?.id ?? null,
      }),
      session.version,
    );
  }

  async function timerAction(timer: BrewTimer, action: "stop" | "cancel" | "observe-elapsed") {
    if (!session) return;
    await runMutation(
      action === "stop" ? "STOP_TIMER" : action === "cancel" ? "CANCEL_TIMER" : "OBSERVE_TIMER_ELAPSED",
      `/api/v1/timers/${timer.id}/${action}`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
      }),
      session.version,
    );
  }

  async function applyCorrection(req: MeasurementRequirement) {
    if (!session || !req.record) return;
    const d = corrDraft[req.id];
    if (!d?.value.trim()) return;
    await runMutation(
      "INSTRUMENT_CORRECTION",
      `/api/v1/measurement-records/${req.record.id}/instrument-corrections`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        corrected_value: d.value.trim(),
        corrected_unit: d.unit || req.record!.display_unit || req.record!.raw_unit,
      }),
      session.version,
    );
  }

  async function applyRevision(req: MeasurementRequirement) {
    if (!session || !req.record) return;
    const d = revDraft[req.id];
    if (!d?.value.trim() || !d.reason.trim()) {
      onError("Revision requires a new value and reason. Original history is preserved.");
      return;
    }
    await runMutation(
      "USER_REVISION",
      `/api/v1/measurement-records/${req.record.id}/revisions`,
      (client_submission_id) => ({
        client_submission_id,
        expected_session_version: session.version,
        raw_value: d.value.trim(),
        raw_unit: d.unit || req.record!.raw_unit,
        reason: d.reason.trim(),
      }),
      session.version,
    );
  }

  if (!session) {
    return (
      <section className="panel brewday-panel" aria-label="Guided Brew Day">
        <h2>Guided Brew Day</h2>
        <p className="muted">
          No active BrewSession. From Recipes → Ready to Brew, create a Brew Plan from an ACTIVE or LOCKED
          recipe version, then start here.
        </p>
        <p className="muted">Draft recipe versions cannot create a Brew Plan.</p>
      </section>
    );
  }

  return (
    <section className="panel brewday-panel" aria-label="Guided Brew Day">
      <header className="brewday-header">
        <div>
          <p className="eyebrow">Brew-Day Copilot</p>
          <h2>{recipeName}</h2>
          <p className="muted">
            Batch {plan?.batch_size ?? "—"} {plan?.batch_size_unit ?? ""}
            {plan?.equipment_snapshot ? " · Equipment profile attached" : ""}
          </p>
        </div>
        <div className="brewday-status" role="status" aria-live="polite">
          <span className={`sync-pill sync-${syncStatus.toLowerCase()}`}>
            Sync: {syncStatus.replaceAll("_", " ")}
          </span>
          <span className="state-pill">Session: {session.status}</span>
          {elapsedDay != null && <span className="state-pill">Elapsed {formatDuration(elapsedDay)}</span>}
          <span className="state-pill">v{session.version}</span>
        </div>
      </header>

      {message && (
        <div className="alert" role="status">
          {message}
          <button type="button" className="ghost" onClick={() => setMessage(null)}>
            Dismiss
          </button>
        </div>
      )}

      <nav className="stage-rail" aria-label="Brew-Day stages">
        {STAGE_SEQUENCE.map((code) => {
          const occ = session.stage_occurrences.find((s) => s.stage_code === code);
          const status = occ?.status ?? "PENDING";
          const current = session.current_stage_code === code;
          return (
            <div
              key={code}
              className={`stage-chip status-${status.toLowerCase()} ${current ? "current" : ""}`}
              aria-current={current ? "step" : undefined}
            >
              <strong>{stageLabel(code)}</strong>
              <span>{status}{occ?.skip_reason ? ` — ${occ.skip_reason}` : ""}</span>
            </div>
          );
        })}
      </nav>
      <p className="muted stage-note">Stages advance forward only. The UI never offers illegal backward transitions.</p>

      {session.status === "PLANNED" && (
        <div className="brewday-actions">
          <button type="button" className="primary brew-cta" disabled={busy} onClick={() => void startSession()}>
            Start Brew Day
          </button>
        </div>
      )}

      {currentStage && !terminal && (
        <article className="current-stage" aria-labelledby="current-stage-title">
          <h3 id="current-stage-title">{stageLabel(currentStage.stage_code)}</h3>
          <p>{stagePurpose(currentStage.stage_code)}</p>
          {paused && (
            <p className="alert" role="status">
              Brew Day is PAUSED. Stage advancement is disabled. Timers continue on wall-clock time — ends_at is not recalculated.
            </p>
          )}

          <h4 className="subhead">Measurements</h4>
          {stageReqs.length === 0 && <p className="muted">No measurements attached to this stage.</p>}
          <ul className="measurement-list">
            {stageReqs.map((req) => (
              <li key={req.id} className={`meas meas-${req.status.toLowerCase()}`}>
                <div className="meas-head">
                  <strong>{req.measurement_code.replaceAll("_", " ")}</strong>
                  <span className="pill">{req.requirement_level}</span>
                  <span className="pill">{req.status}</span>
                </div>
                {req.planned_value != null && (
                  <p className="planned-only">
                    Planned (not measured): {req.planned_value} {req.planned_unit} — {req.planned_kind}
                  </p>
                )}
                {req.status === "CAPTURED" && req.record && (
                  <div className="actual-block">
                    <p>
                      Actual: <strong>{req.record.display_value} {req.record.display_unit}</strong> — {req.record.value_kind}
                      {req.record.confidence ? ` · Confidence ${confLabel(req.record.confidence)}` : ""}
                    </p>
                    {req.record.validation_class && req.record.validation_class !== "OK" && (
                      <p className={`warn-banner warn-${req.record.validation_class.toLowerCase()}`} role="alert">
                        Warning: {req.record.validation_class}
                        {req.record.validation_notes ? ` — ${req.record.validation_notes}` : ""}
                      </p>
                    )}
                    {req.record.corrected_value != null && (
                      <p className="muted">
                        Original reading {req.record.raw_value} {req.record.raw_unit} → Corrected {req.record.corrected_value}{" "}
                        {req.record.corrected_unit}
                      </p>
                    )}
                    <div className="meas-edit">
                      <label>
                        Instrument correction
                        <input
                          value={corrDraft[req.id]?.value ?? ""}
                          onChange={(e) =>
                            setCorrDraft((s) => ({
                              ...s,
                              [req.id]: {
                                value: e.target.value,
                                unit: s[req.id]?.unit || req.record!.display_unit || "SG",
                              },
                            }))
                          }
                        />
                      </label>
                      <button type="button" className="ghost" disabled={busy || paused} onClick={() => void applyCorrection(req)}>
                        Apply correction
                      </button>
                      <label>
                        User revision (reason required)
                        <input
                          placeholder="New value"
                          value={revDraft[req.id]?.value ?? ""}
                          onChange={(e) =>
                            setRevDraft((s) => ({
                              ...s,
                              [req.id]: {
                                value: e.target.value,
                                unit: s[req.id]?.unit || req.record!.raw_unit || "SG",
                                reason: s[req.id]?.reason || "",
                              },
                            }))
                          }
                        />
                        <input
                          placeholder="Reason"
                          value={revDraft[req.id]?.reason ?? ""}
                          onChange={(e) =>
                            setRevDraft((s) => ({
                              ...s,
                              [req.id]: {
                                value: s[req.id]?.value || "",
                                unit: s[req.id]?.unit || req.record!.raw_unit || "SG",
                                reason: e.target.value,
                              },
                            }))
                          }
                        />
                      </label>
                      <button type="button" className="ghost" disabled={busy || paused} onClick={() => void applyRevision(req)}>
                        Submit revision
                      </button>
                    </div>
                  </div>
                )}
                {req.status === "PENDING" && (
                  <form
                    className="capture-form"
                    onSubmit={(e: FormEvent) => {
                      e.preventDefault();
                      void capture(req);
                    }}
                  >
                    <label>
                      Value
                      <input
                        required
                        inputMode="decimal"
                        value={captureDraft[req.id]?.value ?? ""}
                        onChange={(e) =>
                          setCaptureDraft((s) => ({
                            ...s,
                            [req.id]: {
                              value: e.target.value,
                              unit: s[req.id]?.unit || req.planned_unit || "SG",
                              confidence: s[req.id]?.confidence || "HIGH",
                              instrument: s[req.id]?.instrument || "",
                            },
                          }))
                        }
                      />
                    </label>
                    <label>
                      Unit
                      <input
                        value={captureDraft[req.id]?.unit ?? req.planned_unit ?? "SG"}
                        onChange={(e) =>
                          setCaptureDraft((s) => ({
                            ...s,
                            [req.id]: {
                              value: s[req.id]?.value || "",
                              unit: e.target.value,
                              confidence: s[req.id]?.confidence || "HIGH",
                              instrument: s[req.id]?.instrument || "",
                            },
                          }))
                        }
                      />
                    </label>
                    <label>
                      Confidence
                      <select
                        value={captureDraft[req.id]?.confidence ?? "HIGH"}
                        onChange={(e) =>
                          setCaptureDraft((s) => ({
                            ...s,
                            [req.id]: {
                              value: s[req.id]?.value || "",
                              unit: s[req.id]?.unit || req.planned_unit || "SG",
                              confidence: e.target.value,
                              instrument: s[req.id]?.instrument || "",
                            },
                          }))
                        }
                      >
                        <option value="HIGH">HIGH</option>
                        <option value="MEDIUM">MEDIUM</option>
                        <option value="LOW">LOW</option>
                      </select>
                    </label>
                    <label>
                      Instrument (optional)
                      <input
                        value={captureDraft[req.id]?.instrument ?? ""}
                        onChange={(e) =>
                          setCaptureDraft((s) => ({
                            ...s,
                            [req.id]: {
                              value: s[req.id]?.value || "",
                              unit: s[req.id]?.unit || req.planned_unit || "SG",
                              confidence: s[req.id]?.confidence || "HIGH",
                              instrument: e.target.value,
                            },
                          }))
                        }
                      />
                    </label>
                    <button type="submit" className="primary brew-cta" disabled={busy || paused}>
                      Capture measurement
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy || paused}
                      onClick={() => setConfirm({ kind: "miss", payload: req.id })}
                    >
                      Mark Missed
                    </button>
                    <label>
                      Waive reason
                      <input
                        value={waiveReason[req.id] ?? ""}
                        onChange={(e) => setWaiveReason((s) => ({ ...s, [req.id]: e.target.value }))}
                      />
                    </label>
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy || paused}
                      onClick={() => setConfirm({ kind: "waive", payload: req.id })}
                    >
                      Waive
                    </button>
                    <p className="muted tiny">
                      Missed = intended but not captured. Waived = intentionally skipped. Neither creates a measured value.
                    </p>
                  </form>
                )}
              </li>
            ))}
          </ul>

          <h4 className="subhead">Timers</h4>
          <p className="muted">
            Countdown is visual only. Server timestamps are authoritative. Expiration never advances stages, misses measurements, or closes Brew Day.
          </p>
          <div className="timer-start">
            <label>
              Label
              <input value={timerLabel} onChange={(e) => setTimerLabel(e.target.value)} />
            </label>
            <label>
              Target seconds (optional)
              <input value={timerSeconds} onChange={(e) => setTimerSeconds(e.target.value)} inputMode="numeric" />
            </label>
            <button type="button" className="primary brew-cta" disabled={busy || paused} onClick={() => void startTimer()}>
              Start timer
            </button>
          </div>
          <ul className="timer-list">
            {stageTimers.map((timer) => {
              const clock = reconstructTimerDisplay(timer, now);
              return (
                <li key={timer.id} className={`timer-card ${clock.pastDue ? "past-due" : ""}`}>
                  <strong>{timer.label}</strong>
                  <p aria-live="polite">
                    {clock.mode === "countdown" && (
                      <>
                        {clock.pastDue ? "Past due by " : "Remaining "}
                        {formatDuration(Math.abs(clock.remainingSeconds ?? 0))} · {clock.label}
                      </>
                    )}
                    {clock.mode === "countup" && <>Elapsed {formatDuration(clock.elapsedSeconds)}</>}
                    {clock.mode === "terminal" && (
                      <>
                        {timer.status} · elapsed {formatDuration(clock.elapsedSeconds)}
                      </>
                    )}
                  </p>
                  <p className="muted tiny">
                    Started {timer.started_at}
                    {timer.ends_at ? ` · Ends ${timer.ends_at}` : ""}
                  </p>
                  <div className="actions">
                    {timer.status === "RUNNING" && (
                      <>
                        <button type="button" className="ghost" disabled={busy} onClick={() => void timerAction(timer, "stop")}>
                          Stop
                        </button>
                        <button type="button" className="ghost" disabled={busy} onClick={() => void timerAction(timer, "cancel")}>
                          Cancel
                        </button>
                        {clock.pastDue && (
                          <button
                            type="button"
                            className="primary"
                            disabled={busy}
                            onClick={() => void timerAction(timer, "observe-elapsed")}
                          >
                            Observe elapsed
                          </button>
                        )}
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>

          <div className="brewday-actions">
            <button type="button" className="primary brew-cta" disabled={busy || !canAdvance} onClick={() => void advance()}>
              Complete Stage & Continue
            </button>
            <button
              type="button"
              className="ghost"
              disabled={busy || !canAdvance}
              onClick={() => setConfirm({ kind: "skip" })}
            >
              Skip stage…
            </button>
            {!paused ? (
              <button type="button" className="ghost" disabled={busy || session.status !== "IN_PROGRESS"} onClick={() => void pauseResume("PAUSE_SESSION")}>
                Pause Brew Day
              </button>
            ) : (
              <button type="button" className="primary" disabled={busy} onClick={() => void pauseResume("RESUME_SESSION")}>
                Resume Brew Day
              </button>
            )}
            <button type="button" className="ghost danger" disabled={busy || Boolean(terminal)} onClick={() => setConfirm({ kind: "abort" })}>
              Abort Brew Day…
            </button>
          </div>
        </article>
      )}

      {(session.current_stage_code === "BREW_DAY_AUDIT" || report) && report && (
        <article className="audit-panel" aria-labelledby="audit-title">
          <h3 id="audit-title">Brew-Day Audit</h3>
          <p className="muted">Independent evidence dimensions — no overall Brew Score.</p>
          {report.overall_brew_score != null && <p role="alert">Unexpected score present</p>}

          <section>
            <h4>Data Completeness</h4>
            <pre className="audit-block">{JSON.stringify(report.data_completeness, null, 2)}</pre>
          </section>
          <section>
            <h4>Process Adherence</h4>
            <pre className="audit-block">{JSON.stringify(report.process_adherence, null, 2)}</pre>
          </section>
          <section>
            <h4>Planned vs Actual</h4>
            <ul className="list">
              {report.planned_vs_actual.map((row, i) => (
                <li key={i}>
                  <strong>{String(row.measurement_code)}</strong>
                  <span className="row-meta">
                    Planned {String(row.planned_value ?? "—")} ({String(row.planned_kind ?? "n/a")}) · Actual{" "}
                    {String(row.actual_value ?? "not recorded")} ({String(row.actual_kind ?? row.requirement_status)})
                    {row.comparison_available ? ` · Δ ${String(row.delta)}` : ` · ${String(row.unavailable_reason ?? "no delta")}`}
                  </span>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h4>Measurement Quality / Confidence</h4>
            <pre className="audit-block">{JSON.stringify(report.measurement_quality, null, 2)}</pre>
          </section>
          <section>
            <h4>Warnings & Deviations</h4>
            <ul className="list">
              {report.deviations_and_warnings.map((d, i) => (
                <li key={i}>
                  <strong>{String(d.type)}</strong>
                  <span className="row-meta">{JSON.stringify(d)}</span>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h4>Timer Evidence</h4>
            <pre className="audit-block">{JSON.stringify(report.timer_evidence, null, 2)}</pre>
          </section>

          {session.status === "IN_PROGRESS" && session.current_stage_code === "BREW_DAY_AUDIT" && (
            <div className="brewday-actions">
              {pendingRequired.length > 0 && (
                <p className="alert" role="alert">
                  Close blocked — REQUIRED PENDING: {pendingRequired.map((r) => r.measurement_code).join(", ")}
                </p>
              )}
              <button
                type="button"
                className="primary brew-cta"
                disabled={busy || pendingRequired.length > 0}
                onClick={() => void closeSession()}
              >
                Close Brew Day
              </button>
            </div>
          )}
        </article>
      )}

      {session.status === "CLOSED" && (
        <article className="handoff-panel">
          <h3>Brew Day Closed</h3>
          <p>Fermentation handoff is explicit and never automatic.</p>
          <ul className="list">
            <li>Recipe / version baseline preserved on BrewPlan</li>
            <li>Planned OG stays ESTIMATED when present; actual OG only if MEASURED</li>
            <li>Missing Brew-Day evidence remains missing</li>
          </ul>
          <button type="button" className="primary brew-cta" disabled={busy} onClick={() => setConfirm({ kind: "handoff" })}>
            Continue to Fermentation
          </button>
        </article>
      )}

      {session.status === "HANDED_OFF" && (
        <article className="handoff-panel">
          <h3>HANDED_OFF</h3>
          <p className="ok">Boundary recorded. Epic 3 FermentationSession is not created in Epic 2A.</p>
        </article>
      )}

      {confirm && (
        <div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
          <div className="confirm-card">
            <h3 id="confirm-title">Confirm</h3>
            {confirm.kind === "skip" && (
              <>
                <p>
                  Skipping will mark remaining REQUIRED measurements on this stage as MISSED (ADR-004). This cannot be undone as a stage skip.
                </p>
                <label>
                  Skip reason (required)
                  <input value={skipReason} onChange={(e) => setSkipReason(e.target.value)} />
                </label>
                <button type="button" className="primary" disabled={!skipReason.trim() || busy} onClick={() => void confirmSkip()}>
                  Confirm skip
                </button>
              </>
            )}
            {confirm.kind === "miss" && (
              <>
                <p>Mark this measurement Missed? No measured value will be created.</p>
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    const req = requirements.find((r) => r.id === confirm.payload);
                    if (req) void missReq(req);
                  }}
                >
                  Confirm missed
                </button>
              </>
            )}
            {confirm.kind === "waive" && (
              <>
                <p>Waive intentionally skips this measurement. Reason is required. No measured value is created.</p>
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    const req = requirements.find((r) => r.id === confirm.payload);
                    if (req) void waiveReq(req);
                  }}
                >
                  Confirm waive
                </button>
              </>
            )}
            {confirm.kind === "abort" && (
              <>
                <p>
                  Abort is terminal. Existing evidence is preserved. Unresolved measurements are not fabricated. Fermentation handoff will not be available.
                </p>
                <label>
                  Abort reason (required)
                  <input value={abortReason} onChange={(e) => setAbortReason(e.target.value)} />
                </label>
                <button type="button" className="primary danger" disabled={!abortReason.trim() || busy} onClick={() => void abortSession()}>
                  Confirm abort
                </button>
              </>
            )}
            {confirm.kind === "handoff" && (
              <>
                <p>
                  Create the Epic 2 → Epic 3 fermentation handoff boundary? This does not create a FermentationSession. Fermentation tracking begins next.
                </p>
                <button type="button" className="primary" disabled={busy} onClick={() => void handoff()}>
                  Confirm handoff
                </button>
              </>
            )}
            <button type="button" className="ghost" onClick={() => setConfirm(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
      <p className="muted tiny">Brewery {breweryId}</p>
    </section>
  );
}

export { SESSION_KEY, PLAN_KEY };
