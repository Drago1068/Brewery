"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import {
  BrewDetails,
  MEASUREMENT_CONTEXT,
  VoiceProposal,
  formatDuration,
  latestMeasurement,
  measurementCommand,
  newOperationId,
  parseVoiceProposal,
  sessionCommand,
  variance,
} from "@/lib/brew";

export default function BrewDayPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [brew, setBrew] = useState<BrewDetails>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);
  const [receivedAt, setReceivedAt] = useState(0);
  const [note, setNote] = useState("");
  const [voiceText, setVoiceText] = useState("");
  const [voiceDraft, setVoiceDraft] = useState<VoiceProposal | null>(null);
  const [auxName, setAuxName] = useState("Auxiliary timer");
  const [auxSeconds, setAuxSeconds] = useState(300);
  const [measType, setMeasType] = useState("MASH_PH");
  const [measValue, setMeasValue] = useState("");
  const [measMethod, setMeasMethod] = useState(MEASUREMENT_CONTEXT.MASH_PH.method);
  const [sampleTemp, setSampleTemp] = useState("20.00");
  const [phSampleTemp, setPhSampleTemp] = useState("65.00");
  const [compensated, setCompensated] = useState(true);
  const [measVessel, setMeasVessel] = useState(MEASUREMENT_CONTEXT.MASH_PH.vessel ?? "");
  const [waiverReason, setWaiverReason] = useState("");
  const [pitchNote, setPitchNote] = useState("");
  const [repeatReason, setRepeatReason] = useState("Runtime repeat requested by brewer");
  const [abortReason, setAbortReason] = useState("");
  const errorRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      const details = await apiFetch<BrewDetails>(`/brew-sessions/${id}`);
      setBrew(details);
      setReceivedAt(Date.now());
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) router.replace("/login");
      else setError(reason instanceof ApiError ? reason.message : "Could not load the brew session.");
    }
  }, [id, router]);

  useEffect(() => {
    const initial = window.setTimeout(refresh, 0);
    const clock = window.setInterval(() => setTick(Date.now()), 1000);
    const sync = window.setInterval(refresh, 15000);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(clock);
      window.clearInterval(sync);
    };
  }, [refresh]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  const timerSeconds = useMemo(() => {
    const timer = brew?.mash?.timer;
    if (!timer) return 0;
    if (timer.status === "COMPLETED") return timer.elapsed_seconds;
    if (tick === 0 || receivedAt === 0) return timer.elapsed_seconds;
    return timer.elapsed_seconds + Math.max(0, Math.floor((tick - receivedAt) / 1000));
  }, [brew, receivedAt, tick]);

  async function action(path: string, body?: Record<string, unknown>) {
    setBusy(true);
    setError("");
    try {
      const latest = await apiFetch<BrewDetails>(`/brew-sessions/${id}`);
      setBrew(latest);
      setReceivedAt(Date.now());
      await apiFetch(path, {
        method: "POST",
        body: JSON.stringify(sessionCommand(latest.revision, body)),
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

  async function record(
    event: FormEvent<HTMLFormElement>,
    type: string,
    entryMethod = "MANUAL",
    preset?: string,
  ) {
    event.preventDefault();
    const formEl = event.currentTarget;
    const stageId = brew?.current_stage?.id ?? brew?.mash?.id;
    if (!stageId) {
      setError("No active stage is ready for measurements.");
      return;
    }
    const form = formEl ? new FormData(formEl) : null;
    const value = preset ?? (form?.get("value") as string | null) ?? measValue;
    if (!value) {
      setError("Measurement value is required.");
      return;
    }
    const context = MEASUREMENT_CONTEXT[type] ?? MEASUREMENT_CONTEXT.MASH_PH;
    const formMethod =
      (form?.get("method") as string | null) ||
      (type === measType ? measMethod : "") ||
      context.method;
    const formTemp =
      (form?.get("sample_temperature_c") as string | null) ||
      (type === "MASH_PH" ? phSampleTemp : sampleTemp);
    const formVessel =
      (form?.get("vessel") as string | null) ||
      (type === measType ? measVessel : "") ||
      context.vessel;
    const compensatedField = formEl.querySelector('input[name="temperature_compensated"]');
    const formCompensated = compensatedField
      ? form?.get("temperature_compensated") != null
      : compensated;
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/brew-sessions/stages/${stageId}/measurements`, {
        method: "POST",
        body: JSON.stringify(
          measurementCommand(type, value, {
            method: formMethod,
            sample_temperature_c: context.needsSampleTemperature ? formTemp : undefined,
            temperature_compensated: context.needsCompensated ? formCompensated : undefined,
            vessel: context.needsVessel ? formVessel : undefined,
            note: (form?.get("note") as string | null) || null,
            instrument: (form?.get("instrument") as string | null) || null,
            entry_method: entryMethod,
          }),
        ),
      });
      setVoiceDraft(null);
      setVoiceText("");
      setMeasValue("");
      await refresh();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setError(`${reason.message} Refreshing authoritative state…`);
        await refresh();
      } else if (reason instanceof ApiError) {
        setError(reason.message);
      } else {
        setError("Measurement failed.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function uploadPhoto(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("file");
    if (!(file instanceof File) || !file.size) {
      setError("Choose a photo to upload.");
      return;
    }
    const body = new FormData();
    body.set("file", file);
    body.set("operation_id", newOperationId());
    body.set("caption", String(form.get("caption") || ""));
    if (brew?.current_stage?.id) body.set("stage_id", brew.current_stage.id);
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/brew-sessions/${id}/attachments`, { method: "POST", body });
      await refresh();
      event.currentTarget.reset();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Photo upload failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!brew) return <div className="loading" aria-live="polite">Restoring authoritative brew state…</div>;

  const pH = latestMeasurement(brew.mash?.measurements ?? [], "MASH_PH");
  const gravity =
    latestMeasurement(brew.mash?.measurements ?? [], "MASH_GRAVITY") ??
    latestMeasurement(brew.mash?.measurements ?? [], "POST_MASH_GRAVITY");
  const due =
    (brew.due_reminders?.length
      ? brew.due_reminders
      : brew.mash?.notifications.filter((item) => item.status === "DUE")) ?? [];
  const currentName = brew.current_stage?.canonical_stage_type ?? brew.current_stage?.name ?? "Brew day";
  const stages = brew.stages ?? [];
  const pending = stages.find((item) => item.status === "PENDING");
  const mashStage = stages.find((item) => (item.canonical_stage_type || item.name) === "MASH");
  const showStartMash = Boolean(
    mashStage &&
      mashStage.status === "PENDING" &&
      (!brew.mash || brew.mash.status === "PENDING") &&
      !brew.current_stage &&
      pending?.id === mashStage.id,
  );

  return (
    <div className="brew-shell">
      <section className="brew-topbar">
        <div>
          <div className="eyebrow">Brew-Day OS</div>
          <h1>{currentName.replaceAll("_", " ")}</h1>
          <p>
            Session {brew.id.slice(0, 8)} · {currentName} · rev {brew.revision ?? 1}
            {brew.plan_kind ? ` · plan ${brew.plan_kind}` : ""}
          </p>
        </div>
        <span
          className={`status ${brew.status.toLowerCase()}`}
          role="status"
          aria-label="Session status"
        >
          {brew.status}
        </span>
      </section>
      {error && (
        <div
          className="alert error"
          role="alert"
          id="brew-session-error"
          ref={errorRef}
          tabIndex={-1}
        >
          {error}
        </div>
      )}

      <section className="card" aria-label="Stage progress">
        <h2>Stage progress</h2>
        <ol className="timer-list">
          {stages.map((stage) => (
            <li key={stage.id}>
              <strong>{stage.canonical_stage_type ?? stage.name}</strong>
              <span>{stage.status}</span>
              <span>#{stage.occurrence_number}</span>
            </li>
          ))}
        </ol>
      </section>

      {brew.next_required_action && (
        <section className="now-panel" aria-label="What to do now">
          <div className="eyebrow">Now</div>
          <strong>{brew.next_required_action}</strong>
          <small>Authoritative server projection · survives refresh</small>
        </section>
      )}

      {showStartMash ? (
        <section className="card start-stage">
          <div>
            <div className="eyebrow">Current action</div>
            <h2>Ready to start Mash</h2>
            <p>The timer and measurement reminders will be persisted server-side.</p>
          </div>
          <button className="primary giant" disabled={busy} onClick={() => action(`/brew-sessions/${id}/mash/start`)}>
            Start Mash
          </button>
        </section>
      ) : pending && !brew.current_stage && brew.status === "ACTIVE" ? (
        <section className="card start-stage">
          <div>
            <div className="eyebrow">Current action</div>
            <h2>Ready to start {pending.canonical_stage_type ?? pending.name}</h2>
          </div>
          <button
            className="primary giant"
            disabled={busy}
            data-testid="start-current-stage"
            onClick={() => action(`/brew-sessions/stages/${pending.id}/start`)}
          >
            Start {pending.canonical_stage_type ?? pending.name}
          </button>
        </section>
      ) : null}

      {(brew.mash || brew.current_stage) && (
        <>
          <div className="brew-toolbar">
            {brew.status === "ACTIVE" && (
              <button className="secondary dark" disabled={busy} onClick={() => action(`/brew-sessions/${id}/pause`)}>
                Pause session
              </button>
            )}
            {brew.status === "PAUSED" && (
              <button className="primary" disabled={busy} onClick={() => action(`/brew-sessions/${id}/resume`)}>
                Resume session
              </button>
            )}
            {brew.current_stage &&
              brew.current_stage.status === "ACTIVE" &&
              (brew.current_stage.canonical_stage_type || brew.current_stage.name) !== "MASH" && (
              <button
                className="secondary dark"
                disabled={busy}
                onClick={() => action(`/brew-sessions/stages/${brew.current_stage!.id}/complete`)}
              >
                Complete {brew.current_stage.canonical_stage_type ?? brew.current_stage.name}
              </button>
            )}
            {pending && pending.required === false && (
              <button
                className="secondary dark"
                disabled={busy}
                onClick={() =>
                  action(`/brew-sessions/stages/${pending.id}/skip`, {
                    reason: "Optional stage skipped by brewer",
                  })
                }
              >
                Skip {pending.canonical_stage_type ?? pending.name}
              </button>
            )}
          </div>

          {brew.mash?.timer && (
            <section className="timer-panel" aria-label="Mash timer status">
              <span>Mash timer</span>
              <strong data-testid="mash-timer" role="timer" aria-label={`Elapsed ${formatDuration(timerSeconds)}`}>
                {formatDuration(timerSeconds)}
              </strong>
              <div className="timer-track">
                <span
                  style={{
                    width: `${Math.min(100, (timerSeconds / (brew.mash.timer.planned_duration_seconds || 1)) * 100)}%`,
                  }}
                />
              </div>
              <small>
                <span aria-live="polite">{brew.mash.timer.status}</span>
                {" · "}
                Target {brew.planned.mash_duration_minutes} minutes · Restores after refresh
              </small>
            </section>
          )}

          <section className="card" aria-label="Active timers">
            <h2>Active timers</h2>
            <ul className="timer-list" aria-label="Active timers">
              {(brew.timers ?? []).map((timer) => (
                <li key={timer.id}>
                  <strong>{timer.name}</strong>
                  <span>{timer.status}</span>
                  <span role="timer">{formatDuration(timer.elapsed_seconds)}</span>
                  {timer.status === "RUNNING" && (
                    <button className="secondary dark" disabled={busy} onClick={() => action(`/brew-sessions/timers/${timer.id}/pause`)}>
                      Pause
                    </button>
                  )}
                  {timer.status === "PAUSED" && (
                    <button className="secondary dark" disabled={busy} onClick={() => action(`/brew-sessions/timers/${timer.id}/resume`)}>
                      Resume
                    </button>
                  )}
                  {(timer.status === "EXPIRED" || timer.status === "COMPLETED") && (
                    <button className="secondary dark" disabled={busy} onClick={() => action(`/brew-sessions/timers/${timer.id}/acknowledge`)}>
                      Acknowledge
                    </button>
                  )}
                </li>
              ))}
            </ul>
            {brew.current_stage && (
              <form
                className="measurement-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  action(`/brew-sessions/stages/${brew.current_stage!.id}/timers`, {
                    name: `${auxName} ${Date.now() % 10000}`,
                    planned_duration_seconds: auxSeconds,
                  });
                }}
              >
                <label>
                  Auxiliary timer name
                  <input value={auxName} onChange={(event) => setAuxName(event.target.value)} />
                </label>
                <label>
                  Duration (seconds)
                  <input
                    type="number"
                    min={1}
                    value={auxSeconds}
                    onChange={(event) => setAuxSeconds(Number(event.target.value))}
                  />
                </label>
                <button className="primary" disabled={busy}>
                  Start auxiliary timer
                </button>
              </form>
            )}
          </section>

          {due.length > 0 && (
            <section className="prompts" aria-label="Required actions" aria-live="polite">
              {due.map((item) => (
                <div className="prompt" key={item.id}>
                  <span className="prompt-icon">!</span>
                  <div>
                    <strong>{item.message}</strong>
                    <small>Required observation</small>
                  </div>
                  {item.status === "DUE" && (
                    <button
                      className="secondary dark"
                      disabled={busy}
                      onClick={() => action(`/brew-sessions/reminders/${item.id}/acknowledge`)}
                    >
                      Acknowledge
                    </button>
                  )}
                </div>
              ))}
            </section>
          )}

          {brew.mash?.status === "ACTIVE" && (
            <div className="measurement-grid">
              <MeasurementCard title="Mash pH" target={`${brew.planned.mash_ph} ± ${brew.planned.mash_ph_tolerance}`} done={pH}>
                <form
                  onSubmit={(event) => record(event, "MASH_PH")}
                  className="measurement-form"
                  aria-describedby={error ? "brew-session-error" : undefined}
                >
                  <label>
                    pH reading
                    <input name="value" type="number" min="0" max="14" step="0.01" required inputMode="decimal" />
                  </label>
                  <label>
                    Method
                    <select name="method" defaultValue="METER" aria-label="pH method">
                      {MEASUREMENT_CONTEXT.MASH_PH.methods.map((method) => (
                        <option key={method} value={method}>
                          {method}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Sample temperature (°C)
                    <input name="sample_temperature_c" type="number" step="0.01" defaultValue="65.00" required />
                  </label>
                  <label>
                    Temperature compensated
                    <input name="temperature_compensated" type="checkbox" defaultChecked />
                  </label>
                  <label>
                    Instrument
                    <input name="instrument" placeholder="Calibrated meter" />
                  </label>
                  <label className="full">
                    Note
                    <input name="note" placeholder="Optional brew-day note" />
                  </label>
                  <button type="submit" className="primary full" disabled={busy}>
                    Record pH
                  </button>
                </form>
              </MeasurementCard>
              <MeasurementCard
                title="Mash gravity"
                target={`${brew.planned.mash_gravity} ± ${brew.planned.mash_gravity_tolerance} SG`}
                done={gravity}
              >
                <form
                  onSubmit={(event) =>
                    record(event, brew.plan_kind?.toLowerCase().includes("legacy") ? "MASH_GRAVITY" : "POST_MASH_GRAVITY")
                  }
                  className="measurement-form"
                  aria-describedby={error ? "brew-session-error" : undefined}
                >
                  <label>
                    Gravity reading
                    <input name="value" type="number" min="0.9" max="1.3" step="0.001" required inputMode="decimal" />
                  </label>
                  <label>
                    Method
                    <select name="method" defaultValue="HYDROMETER" aria-label="Gravity method">
                      {MEASUREMENT_CONTEXT.POST_MASH_GRAVITY.methods.map((method) => (
                        <option key={method} value={method}>
                          {method}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Sample temperature (°C)
                    <input name="sample_temperature_c" type="number" step="0.01" defaultValue="20.00" required />
                  </label>
                  <label>
                    Instrument
                    <input name="instrument" placeholder="Hydrometer" />
                  </label>
                  <label className="full">
                    Note
                    <input name="note" placeholder="Optional brew-day note" />
                  </label>
                  <button type="submit" className="primary full" disabled={busy}>
                    Record gravity
                  </button>
                </form>
              </MeasurementCard>
            </div>
          )}

          {brew.current_stage?.status === "ACTIVE" && (
            <section className="card" aria-label="Measurements">
              <h2>Measurements</h2>
              <form
                className="measurement-form"
                aria-describedby={error ? "brew-session-error" : undefined}
                onSubmit={(event) => {
                  event.preventDefault();
                  record(event, measType);
                }}
              >
                <label>
                  Type
                  <select
                    aria-label="Measurement type"
                    value={measType}
                    onChange={(event) => {
                      const next = event.target.value;
                      setMeasType(next);
                      const context = MEASUREMENT_CONTEXT[next];
                      setMeasMethod(context.method);
                      setMeasVessel(context.vessel ?? "");
                    }}
                  >
                    {Object.keys(MEASUREMENT_CONTEXT).map((type) => (
                      <option key={type} value={type}>
                        {type}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Value
                  <input
                    name="value"
                    aria-label="Measurement value"
                    value={measValue}
                    onChange={(event) => setMeasValue(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Method
                  <select
                    name="method"
                    aria-label="Measurement method"
                    value={measMethod}
                    onChange={(event) => setMeasMethod(event.target.value)}
                  >
                    {(MEASUREMENT_CONTEXT[measType]?.methods ?? []).map((method) => (
                      <option key={method} value={method}>
                        {method}
                      </option>
                    ))}
                  </select>
                </label>
                {MEASUREMENT_CONTEXT[measType]?.needsSampleTemperature && (
                  <label>
                    Sample temperature (°C)
                    <input
                      name="sample_temperature_c"
                      type="number"
                      step="0.01"
                      value={measType === "MASH_PH" ? phSampleTemp : sampleTemp}
                      onChange={(event) =>
                        measType === "MASH_PH"
                          ? setPhSampleTemp(event.target.value)
                          : setSampleTemp(event.target.value)
                      }
                      required
                    />
                  </label>
                )}
                {MEASUREMENT_CONTEXT[measType]?.needsCompensated && (
                  <label>
                    Temperature compensated
                    <input
                      name="temperature_compensated"
                      type="checkbox"
                      checked={compensated}
                      onChange={(event) => setCompensated(event.target.checked)}
                    />
                  </label>
                )}
                {MEASUREMENT_CONTEXT[measType]?.needsVessel && (
                  <label>
                    Vessel
                    <input
                      name="vessel"
                      value={measVessel}
                      onChange={(event) => setMeasVessel(event.target.value)}
                      required
                    />
                  </label>
                )}
                <button className="primary" disabled={busy}>
                  Record measurement
                </button>
              </form>
            </section>
          )}

          {brew.mash?.status === "ACTIVE" && (
            <section className="card voice-card">
              <div className="eyebrow">Voice confirmation boundary</div>
              <h2>Confirm before commit</h2>
              <p>Speech is draft input only. Nothing is recorded until you confirm the parsed value.</p>
              <label>
                Transcript
                <input
                  value={voiceText}
                  onChange={(event) => setVoiceText(event.target.value)}
                  placeholder="five point two pH"
                />
              </label>
              <button className="secondary dark" type="button" onClick={() => setVoiceDraft(parseVoiceProposal(voiceText))}>
                Parse transcript
              </button>
              {voiceDraft && (
                <form
                  className="voice-confirm"
                  role="dialog"
                  aria-modal="false"
                  aria-label="Voice measurement confirmation"
                  onSubmit={(event) =>
                    record(
                      event,
                      voiceDraft.field === "MASH_GRAVITY" ? "MASH_GRAVITY" : "MASH_PH",
                      "VOICE_CONFIRMED",
                      voiceDraft.value,
                    )
                  }
                >
                  <p>
                    Proposed {voiceDraft.field}:{" "}
                    <strong>
                      {voiceDraft.value} {voiceDraft.unit}
                    </strong>
                  </p>
                  <label>
                    Corrected value
                    <input
                      name="value"
                      value={voiceDraft.value}
                      onChange={(event) => setVoiceDraft({ ...voiceDraft, value: event.target.value })}
                    />
                  </label>
                  <button className="primary" disabled={busy}>
                    Confirm voice measurement
                  </button>
                  <button className="secondary dark" type="button" disabled={busy} onClick={() => setVoiceDraft(null)}>
                    Reject proposal
                  </button>
                </form>
              )}
            </section>
          )}

          <section className="card" aria-label="Upcoming additions">
            <h2>Upcoming additions</h2>
            <ul className="timer-list">
              {(brew.requirements ?? [])
                .filter((item) => item.class === "ADDITION")
                .map((item) => (
                  <li key={item.id}>
                    <strong>{item.definition_key ?? "Addition"}</strong>
                    <span>{item.status}</span>
                    <span>
                      {item.planned_amount} {item.planned_unit}
                    </span>
                    {item.status === "PENDING" && brew.status === "ACTIVE" && (
                      <>
                        <button
                          className="secondary dark"
                          disabled={busy}
                          onClick={() =>
                            action(`/brew-sessions/${id}/requirements/${item.id}/additions`, {
                              quantity: item.planned_amount,
                              unit: item.planned_unit,
                            })
                          }
                        >
                          Record executed
                        </button>
                        <button
                          className="secondary dark"
                          disabled={busy}
                          onClick={() =>
                            action(`/brew-sessions/${id}/requirements/${item.id}/additions`, {
                              quantity: item.planned_amount,
                              unit: item.planned_unit,
                              late_reason: "Late addition recorded after the governing stage closed",
                            })
                          }
                        >
                          Record late
                        </button>
                      </>
                    )}
                  </li>
                ))}
            </ul>
            {(brew.additions ?? []).map((item) => (
              <div key={item.id}>
                <small>
                  Event {item.id.slice(0, 8)} · {item.status} · {item.actual_quantity} {item.actual_unit}
                </small>
                <button
                  className="secondary dark"
                  disabled={busy}
                  onClick={() =>
                    action(`/brew-sessions/${id}/addition-events/${item.id}/corrections`, {
                      quantity: item.actual_quantity ?? item.planned_amount,
                      unit: item.actual_unit ?? item.planned_unit,
                      reason: "Corrected addition quantity on brew day",
                    })
                  }
                >
                  Correct addition
                </button>
              </div>
            ))}
          </section>

          <section className="card" aria-label="Checklists and waivers">
            <h2>Checklists and waivers</h2>
            <ul className="timer-list">
              {(brew.requirements ?? [])
                .filter(
                  (item) =>
                    item.class === "CHECKLIST" &&
                    item.status === "PENDING" &&
                    item.definition_key !== "YEAST_ADDITION_FACT",
                )
                .map((item) => (
                  <li key={`checklist-${item.id}`}>
                    <strong>{item.definition_key ?? "Checklist"}</strong>
                    <button
                      className="primary"
                      disabled={busy}
                      data-testid={`complete-checklist-${item.definition_key ?? item.id}`}
                      onClick={() =>
                        action(`/brew-sessions/${id}/requirements/${item.id}/complete`, {})
                      }
                    >
                      Mark complete
                    </button>
                  </li>
                ))}
              {(brew.requirements ?? [])
                .filter((item) => {
                  const activeId = brew.current_stage?.id ?? brew.mash?.id;
                  const onActiveStage =
                    !item.stage_instance_id || !activeId || item.stage_instance_id === activeId;
                  return (
                    Boolean(item.required) &&
                    Boolean(item.waivable) &&
                    (item.status === "PENDING" || item.status === "DUE") &&
                    onActiveStage
                  );
                })
                .map((item) => (
                  <li key={item.id}>
                    <strong>{item.definition_key ?? item.class}</strong>
                    <input
                      placeholder="Waiver reason (required)"
                      aria-label="Waiver reason (required)"
                      value={waiverReason}
                      onChange={(event) => setWaiverReason(event.target.value)}
                    />
                    <button
                      className="secondary dark"
                      disabled={busy || waiverReason.length < 10}
                      onClick={() =>
                        action(`/brew-sessions/${id}/requirements/${item.id}/waivers`, {
                          reason: waiverReason,
                        })
                      }
                    >
                      Waive
                    </button>
                  </li>
                ))}
            </ul>
          </section>

          {brew.mash?.status === "ACTIVE" && (
            <button
              className="complete-button"
              disabled={busy || !pH || !gravity}
              onClick={() => action(`/brew-sessions/stages/${brew.mash!.id}/complete`)}
            >
              {!pH || !gravity ? "Record required measurements to complete Mash" : "Complete Mash"}
            </button>
          )}

          <section className="card">
            <h2>Notes and media</h2>
            <form
              className="measurement-form"
              onSubmit={(event) => {
                event.preventDefault();
                action(`/brew-sessions/${id}/notes`, { body: note });
                setNote("");
              }}
            >
              <label className="full">
                Brew-day note
                <input value={note} onChange={(event) => setNote(event.target.value)} maxLength={4000} />
              </label>
              <button className="primary" disabled={busy || !note}>
                Add note
              </button>
            </form>
            <ul className="note-list">
              {(brew.notes ?? []).map((item) => (
                <li key={item.id}>{item.body}</li>
              ))}
            </ul>
            <form className="measurement-form" onSubmit={uploadPhoto}>
              <label>
                Photo
                <input name="file" type="file" accept="image/png,image/jpeg,image/webp" />
              </label>
              <label>
                Caption
                <input name="caption" maxLength={1000} />
              </label>
              <button className="primary" disabled={busy}>
                Upload photo
              </button>
            </form>
            <ul className="note-list">
              {(brew.attachments ?? []).map((item) => (
                <li key={item.id}>
                  {item.caption || item.id.slice(0, 8)} · {item.content_type}
                </li>
              ))}
            </ul>
          </section>

          <section className="card" aria-label="Repeat return and pitch">
            <h2>Session actions</h2>
            {mashStage && mashStage.status === "COMPLETED" && (
              <>
                <label>
                  Repeat/return reason
                  <input value={repeatReason} onChange={(event) => setRepeatReason(event.target.value)} />
                </label>
                <button
                  className="secondary dark"
                  disabled={busy}
                  onClick={() => action(`/brew-sessions/stages/${mashStage.id}/repeat`, { reason: repeatReason })}
                >
                  Repeat Mash
                </button>
                <button
                  className="secondary dark"
                  disabled={busy}
                  onClick={() => action(`/brew-sessions/stages/${mashStage.id}/return`, { reason: repeatReason })}
                >
                  Controlled return
                </button>
              </>
            )}
            <label>
              Yeast pitch note
              <input value={pitchNote} onChange={(event) => setPitchNote(event.target.value)} />
            </label>
            <button
              className="primary"
              disabled={busy || !pitchNote}
              onClick={() => action(`/brew-sessions/${id}/pitch-handoff`, { yeast_addition_note: pitchNote })}
            >
              Record yeast pitch
            </button>
            <button className="primary" disabled={busy} onClick={() => action(`/brew-sessions/${id}/complete`)}>
              Complete brew session
            </button>
            <label>
              Abort reason
              <input value={abortReason} onChange={(event) => setAbortReason(event.target.value)} />
            </label>
            <button
              className="secondary dark"
              disabled={busy || abortReason.length < 10}
              onClick={() => action(`/brew-sessions/${id}/abort`, { reason: abortReason })}
            >
              Abort session
            </button>
          </section>

          <section className="performance card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Persisted evidence</div>
                <h2>Mash performance</h2>
              </div>
            </div>
            <div className="performance-grid">
              <Performance label="Mash temperature" target={`${brew.planned.mash_temperature} °F`} actual="See stage measurements" />
              <Performance
                label="Mash pH"
                target={brew.planned.mash_ph}
                actual={pH?.value}
                variance={variance(pH?.value, brew.planned.mash_ph)}
                outside={Boolean(pH?.deviation)}
              />
              <Performance
                label="Mash gravity"
                target={`${brew.planned.mash_gravity} SG`}
                actual={gravity ? `${gravity.value} SG` : undefined}
                variance={variance(gravity?.value, brew.planned.mash_gravity)}
                outside={Boolean(gravity?.deviation)}
              />
            </div>
          </section>

          <section className="journal card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Automatic record</div>
                <h2>Brew journal</h2>
              </div>
              <span>{brew.journal.length} events</span>
            </div>
            <ol>
              {[...brew.journal].reverse().map((event) => (
                <li key={event.id}>
                  <time>
                    {new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </time>
                  <div>
                    <strong>{event.message}</strong>
                    <small>{event.event_type.replaceAll("_", " ")}</small>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </>
      )}
    </div>
  );
}

function MeasurementCard({
  title,
  target,
  done,
  children,
}: {
  title: string;
  target: string;
  done?: { value: string; unit: string; deviation?: object };
  children: React.ReactNode;
}) {
  return (
    <section className={`card measurement-card ${done ? "done" : ""}`}>
      <div className="card-title">
        <div>
          <h2>{title}</h2>
          <p>Target {target}</p>
        </div>
        {done && <span className="check">✓</span>}
      </div>
      {done ? (
        <div className="recorded-value">
          <strong>{done.value}</strong>
          <span>{done.unit}</span>
          {done.deviation && <em>Outside tolerance</em>}
        </div>
      ) : (
        children
      )}
    </section>
  );
}

function Performance({
  label,
  target,
  actual,
  variance: delta,
  outside,
}: {
  label: string;
  target: string;
  actual?: string;
  variance?: string;
  outside?: boolean;
}) {
  return (
    <div>
      <h3>{label}</h3>
      <dl>
        <div>
          <dt>Target</dt>
          <dd>{target}</dd>
        </div>
        <div>
          <dt>Actual</dt>
          <dd>{actual ?? "Pending"}</dd>
        </div>
        {delta && (
          <div>
            <dt>Variance</dt>
            <dd>{delta}</dd>
          </div>
        )}
      </dl>
      <span className={`result ${outside ? "outside" : actual ? "within" : "pending"}`}>
        {outside ? "Outside tolerance" : actual ? "Within tolerance" : "Not recorded"}
      </span>
    </div>
  );
}
