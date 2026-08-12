"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { ApiError, apiFetch } from "@/lib/api";
import { BrewDetails, formatDuration, latestMeasurement, variance } from "@/lib/brew";

export default function BrewDayPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [brew, setBrew] = useState<BrewDetails>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(0);
  const [receivedAt, setReceivedAt] = useState(0);

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

  const timerSeconds = useMemo(() => {
    const timer = brew?.mash?.timer;
    if (!timer) return 0;
    if (timer.status === "COMPLETED") return timer.elapsed_seconds;
    if (tick === 0 || receivedAt === 0) return timer.elapsed_seconds;
    return timer.elapsed_seconds + Math.max(0, Math.floor((tick - receivedAt) / 1000));
  }, [brew, receivedAt, tick]);

  async function action(path: string) {
    setBusy(true); setError("");
    try { await apiFetch(path, { method: "POST" }); await refresh(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Action failed."); }
    finally { setBusy(false); }
  }

  async function record(event: FormEvent<HTMLFormElement>, type: "MASH_PH" | "MASH_GRAVITY") {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch(`/brew-sessions/stages/${brew?.mash?.id}/measurements`, {
        method: "POST",
        body: JSON.stringify({
          measurement_type: type,
          value: form.get("value"),
          unit: type === "MASH_PH" ? "pH" : "SG",
          note: form.get("note") || null,
          instrument: form.get("instrument") || null,
        }),
      });
      await refresh();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Measurement failed."); }
    finally { setBusy(false); }
  }

  if (!brew) return <div className="loading" aria-live="polite">Restoring authoritative brew state…</div>;

  const pH = latestMeasurement(brew.mash?.measurements ?? [], "MASH_PH");
  const gravity = latestMeasurement(brew.mash?.measurements ?? [], "MASH_GRAVITY");
  const due = brew.mash?.notifications.filter((item) => item.status === "DUE") ?? [];

  return (
    <div className="brew-shell">
      <section className="brew-topbar">
        <div><div className="eyebrow">Brew-Day Mode</div><h1>Mash</h1><p>Session {brew.id.slice(0, 8)}</p></div>
        <span className={`status ${brew.status.toLowerCase()}`}>{brew.status}</span>
      </section>
      {error && <div className="alert error" role="alert">{error}</div>}

      {!brew.mash ? (
        <section className="card start-stage">
          <div><div className="eyebrow">Current action</div><h2>Ready to start Mash</h2><p>The timer and measurement reminders will be persisted server-side.</p></div>
          <button className="primary giant" disabled={busy} onClick={() => action(`/brew-sessions/${id}/mash/start`)}>Start Mash</button>
        </section>
      ) : (
        <>
          <section className="timer-panel" aria-live="polite">
            <span>Mash timer</span>
            <strong data-testid="mash-timer">{formatDuration(timerSeconds)}</strong>
            <div className="timer-track"><span style={{ width: `${Math.min(100, (timerSeconds / brew.mash.timer!.planned_duration_seconds) * 100)}%` }} /></div>
            <small>Target {brew.planned.mash_duration_minutes} minutes · Restores after refresh</small>
          </section>

          {due.length > 0 && <section className="prompts" aria-label="Required actions">{due.map((item) => <div className="prompt" key={item.id}><span className="prompt-icon">!</span><div><strong>{item.message}</strong><small>Required Mash observation</small></div></div>)}</section>}

          {brew.mash.status === "ACTIVE" && (
            <div className="measurement-grid">
              <MeasurementCard title="Mash pH" target={`${brew.planned.mash_ph} ± ${brew.planned.mash_ph_tolerance}`} done={pH}>
                <form onSubmit={(event) => record(event, "MASH_PH")} className="measurement-form">
                  <label>pH reading<input name="value" type="number" min="0" max="14" step="0.01" required inputMode="decimal" /></label>
                  <label>Instrument<input name="instrument" placeholder="Calibrated meter" /></label>
                  <label className="full">Note<input name="note" placeholder="Optional brew-day note" /></label>
                  <button className="primary full" disabled={busy}>Record pH</button>
                </form>
              </MeasurementCard>
              <MeasurementCard title="Mash gravity" target={`${brew.planned.mash_gravity} ± ${brew.planned.mash_gravity_tolerance} SG`} done={gravity}>
                <form onSubmit={(event) => record(event, "MASH_GRAVITY")} className="measurement-form">
                  <label>Gravity reading<input name="value" type="number" min="1" max="1.2" step="0.001" required inputMode="decimal" /></label>
                  <label>Instrument<input name="instrument" placeholder="Hydrometer" /></label>
                  <label className="full">Note<input name="note" placeholder="Optional brew-day note" /></label>
                  <button className="primary full" disabled={busy}>Record gravity</button>
                </form>
              </MeasurementCard>
            </div>
          )}

          {brew.mash.status === "ACTIVE" && (
            <button className="complete-button" disabled={busy || !pH || !gravity} onClick={() => action(`/brew-sessions/stages/${brew.mash!.id}/complete`)}>
              {!pH || !gravity ? "Record required measurements to complete Mash" : "Complete Mash"}
            </button>
          )}

          <section className="performance card">
            <div className="section-heading"><div><div className="eyebrow">Persisted evidence</div><h2>Mash performance</h2></div></div>
            <div className="performance-grid">
              <Performance label="Mash temperature" target={`${brew.planned.mash_temperature} °F`} actual="Not captured in Phase 1A" />
              <Performance label="Mash pH" target={brew.planned.mash_ph} actual={pH?.value} variance={variance(pH?.value, brew.planned.mash_ph)} outside={Boolean(pH?.deviation)} />
              <Performance label="Mash gravity" target={`${brew.planned.mash_gravity} SG`} actual={gravity ? `${gravity.value} SG` : undefined} variance={variance(gravity?.value, brew.planned.mash_gravity)} outside={Boolean(gravity?.deviation)} />
            </div>
          </section>

          <section className="journal card">
            <div className="section-heading"><div><div className="eyebrow">Automatic record</div><h2>Brew journal</h2></div><span>{brew.journal.length} events</span></div>
            <ol>{[...brew.journal].reverse().map((event) => <li key={event.id}><time>{new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time><div><strong>{event.message}</strong><small>{event.event_type.replaceAll("_", " ")}</small></div></li>)}</ol>
          </section>
        </>
      )}
    </div>
  );
}

function MeasurementCard({ title, target, done, children }: { title: string; target: string; done?: { value: string; unit: string; deviation?: object }; children: React.ReactNode }) {
  return <section className={`card measurement-card ${done ? "done" : ""}`}><div className="card-title"><div><h2>{title}</h2><p>Target {target}</p></div>{done && <span className="check">✓</span>}</div>{done ? <div className="recorded-value"><strong>{done.value}</strong><span>{done.unit}</span>{done.deviation && <em>Outside tolerance</em>}</div> : children}</section>;
}

function Performance({ label, target, actual, variance: delta, outside }: { label: string; target: string; actual?: string; variance?: string; outside?: boolean }) {
  return <div><h3>{label}</h3><dl><div><dt>Target</dt><dd>{target}</dd></div><div><dt>Actual</dt><dd>{actual ?? "Pending"}</dd></div>{delta && <div><dt>Variance</dt><dd>{delta}</dd></div>}</dl><span className={`result ${outside ? "outside" : actual && actual !== "Not captured in Phase 1A" ? "within" : "pending"}`}>{outside ? "Outside tolerance" : actual && actual !== "Not captured in Phase 1A" ? "Within tolerance" : "Not recorded"}</span></div>;
}
