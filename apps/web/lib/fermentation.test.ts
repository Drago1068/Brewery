import { describe, expect, it } from "vitest";

import {
  activeFermentationStage,
  dueReminders,
  fermentationCommand,
  measurementCommand,
  type FermentationDetails,
} from "./fermentation";

const base: FermentationDetails = {
  id: "fs-1",
  brew_session_id: "bs-1",
  status: "ACTIVE",
  revision: 3,
  stages: [
    {
      id: "st-1",
      canonical_stage_type: "ACTIVE_FERMENTATION",
      occurrence_number: 1,
      status: "ACTIVE",
    },
  ],
  measurements: [],
  reminders: [
    { id: "r-1", status: "DUE", message: "Record gravity" },
    { id: "r-2", status: "ACKNOWLEDGED", message: "Old" },
  ],
  timers: [],
  waivers: [],
};

describe("fermentation helpers", () => {
  it("builds revision-bound commands without client authority fields", () => {
    const body = fermentationCommand(4, { override: true });
    expect(body.expected_revision).toBe(4);
    expect(body.override).toBe(true);
    expect(typeof body.operation_id).toBe("string");
    expect(body).not.toHaveProperty("status");
  });

  it("builds measurement payloads for API submission", () => {
    const body = measurementCommand({
      measurement_type: "FERMENTATION_GRAVITY",
      value: "1.020",
      unit: "SG",
      observed_at: "2026-01-01T00:00:00Z",
      stage_instance_id: "st-1",
      note: "worksheet note",
      expected_revision: 2,
    });
    expect(body.measurement_type).toBe("FERMENTATION_GRAVITY");
    expect(body.note).toBe("worksheet note");
    expect(body.expected_revision).toBe(2);
  });

  it("selects active stage and due reminders from authoritative read model", () => {
    expect(activeFermentationStage(base)?.id).toBe("st-1");
    expect(dueReminders(base)).toHaveLength(1);
  });
});
