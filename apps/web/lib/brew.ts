export type Measurement = {
  id: string;
  type: string;
  value: string;
  unit: string;
  measured_at: string;
  note?: string;
  instrument?: string;
  provenance: string;
  correction_of_id?: string;
  deviation?: { variance: string; tolerance: string; status: string };
};

export type BrewDetails = {
  id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  revision?: number;
  plan_kind?: string | null;
  logical_plan_hash?: string | null;
  planned: {
    mash_temperature: string;
    temperature_unit: string;
    mash_ph: string;
    mash_ph_tolerance: string;
    mash_gravity: string;
    mash_gravity_tolerance: string;
    mash_duration_minutes: number;
  };
  mash: null | {
    id: string;
    status: string;
    timer: null | {
      id: string;
      status: string;
      started_at: string;
      planned_duration_seconds: number;
      elapsed_seconds: number;
      completed_at?: string;
    };
    measurements: Measurement[];
    notifications: Array<{
      id: string;
      type: string;
      message: string;
      status: string;
      due_at: string;
    }>;
  };
  current_stage?: { id: string; name: string; status: string; canonical_stage_type?: string };
  stages?: Array<{
    id: string;
    name: string;
    status: string;
    occurrence_number: number;
    required: boolean;
  }>;
  timers?: Array<{
    id: string;
    name: string;
    status: string;
    planned_duration_seconds: number;
    elapsed_seconds: number;
    deadline_at?: string;
  }>;
  due_reminders?: Array<{
    id: string;
    message: string;
    status: string;
    type: string;
  }>;
  requirements?: Array<{
    id: string;
    class: string;
    status: string;
    required: boolean;
    definition_key?: string;
    planned_amount?: string;
    planned_unit?: string;
  }>;
  additions?: Array<{ id: string; status: string; actual_quantity?: string }>;
  notes?: Array<{ id: string; body: string; created_at: string }>;
  next_required_action?: string | null;
  journal: Array<{
    id: string;
    event_type: string;
    message: string;
    created_at: string;
  }>;
};

export type VoiceProposal = {
  transcript: string;
  field: string;
  value: string;
  unit: string;
  action: string;
  committed: string;
};

export function formatDuration(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, "0")).join(":");
}

export function latestMeasurement(
  measurements: Measurement[],
  type: Measurement["type"],
): Measurement | undefined {
  return measurements.filter((item) => item.type === type).at(-1);
}

export function variance(actual: string | undefined, target: string): string | undefined {
  if (actual === undefined) return undefined;
  const value = Number(actual) - Number(target);
  const precision = target.includes(".") ? target.split(".")[1].length : 0;
  return `${value >= 0 ? "+" : ""}${value.toFixed(precision)}`;
}

const ONES: Record<string, number> = {
  zero: 0,
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
};
const TENS: Record<string, number> = {
  twenty: 20,
  thirty: 30,
  forty: 40,
  fifty: 50,
  sixty: 60,
  seventy: 70,
  eighty: 80,
  ninety: 90,
};

function numberFromTokens(tokens: string[]): string | null {
  let whole: number | null = null;
  const fraction: string[] = [];
  let inFraction = false;
  for (const token of tokens) {
    if (token === "." || token === "point") {
      inFraction = true;
      continue;
    }
    if (/^\d+(\.\d+)?$/.test(token)) {
      if (inFraction) fraction.push(token.replace(".", ""));
      else whole = whole === null ? Number(token) : Number(`${whole}${token}`);
      continue;
    }
    if (token in TENS) {
      whole = whole === null ? TENS[token] : whole + TENS[token];
      continue;
    }
    if (token in ONES) {
      const value = ONES[token];
      if (inFraction) fraction.push(String(value));
      else if (whole !== null && whole >= 20 && whole % 10 === 0) whole += value;
      else if (whole === null) whole = value;
      else whole = Number(`${whole}${value}`);
    }
  }
  if (whole === null && fraction.length === 0) return null;
  if (fraction.length) return `${whole ?? 0}.${fraction.join("")}`;
  return String(whole);
}

/** Idempotency keys must work on non-secure HTTP origins (Docker e2e uses http://web:3000). */
export function newOperationId(): string {
  const c = typeof globalThis !== "undefined" ? globalThis.crypto : undefined;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  if (c && typeof c.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    c.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return `op-${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
}

export function parseVoiceProposal(transcript: string): VoiceProposal | null {
  if (!transcript.trim()) return null;
  const lowered = transcript.toLowerCase().trim();
  const value = numberFromTokens(lowered.replaceAll("-", " ").split(/\s+/));
  if (!value) return null;
  const gravity = lowered.includes("gravity");
  return {
    transcript,
    field: gravity ? "MASH_GRAVITY" : "MASH_PH",
    value,
    unit: gravity ? "SG" : "pH",
    action: "record_measurement",
    committed: "false",
  };
}
