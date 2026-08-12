export type Measurement = {
  id: string;
  type: "MASH_PH" | "MASH_GRAVITY";
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
  journal: Array<{
    id: string;
    event_type: string;
    message: string;
    created_at: string;
  }>;
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

