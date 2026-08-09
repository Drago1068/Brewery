/** Reconstruct timer display from authoritative server timestamps (visual only). */

export type TimerClock = {
  mode: "countdown" | "countup" | "terminal";
  remainingSeconds: number | null;
  elapsedSeconds: number;
  label: string;
  pastDue: boolean;
};

function parseTs(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

export function reconstructTimerDisplay(
  timer: {
    status: string;
    started_at: string | null;
    ends_at: string | null;
    elapsed_at: string | null;
    stopped_at: string | null;
    cancelled_at: string | null;
    computed_past_due?: boolean;
    target_duration_seconds?: number | null;
  },
  nowMs: number = Date.now(),
): TimerClock {
  const started = parseTs(timer.started_at) ?? nowMs;
  const ends = parseTs(timer.ends_at);
  const terminalAt =
    parseTs(timer.cancelled_at) ??
    parseTs(timer.stopped_at) ??
    parseTs(timer.elapsed_at);

  if (timer.status === "CANCELLED" || timer.status === "STOPPED" || timer.status === "ELAPSED") {
    const endRef = terminalAt ?? nowMs;
    return {
      mode: "terminal",
      remainingSeconds: 0,
      elapsedSeconds: Math.max(0, Math.floor((endRef - started) / 1000)),
      label: timer.status,
      pastDue: timer.status === "ELAPSED" || Boolean(timer.computed_past_due),
    };
  }

  const elapsedSeconds = Math.max(0, Math.floor((nowMs - started) / 1000));
  if (ends != null) {
    const remaining = Math.floor((ends - nowMs) / 1000);
    const pastDue = remaining <= 0 || Boolean(timer.computed_past_due);
    return {
      mode: "countdown",
      remainingSeconds: remaining,
      elapsedSeconds,
      label: pastDue ? "PAST DUE" : "RUNNING",
      pastDue,
    };
  }

  return {
    mode: "countup",
    remainingSeconds: null,
    elapsedSeconds,
    label: "RUNNING",
    pastDue: false,
  };
}

export function formatDuration(totalSeconds: number): string {
  const sign = totalSeconds < 0 ? "-" : "";
  const abs = Math.abs(totalSeconds);
  const h = Math.floor(abs / 3600);
  const m = Math.floor((abs % 3600) / 60);
  const s = abs % 60;
  if (h > 0) return `${sign}${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${sign}${m}:${String(s).padStart(2, "0")}`;
}
