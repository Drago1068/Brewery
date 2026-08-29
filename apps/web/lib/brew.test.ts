import { describe, expect, it } from "vitest";

import {
  formatDuration,
  latestMeasurement,
  measurementCommand,
  newOperationId,
  parseVoiceProposal,
  sessionCommand,
  variance,
  type Measurement,
} from "./brew";

describe("brew presentation helpers", () => {
  it("formats a persisted elapsed duration", () => {
    expect(formatDuration(3661)).toBe("01:01:01");
    expect(formatDuration(-2)).toBe("00:00:00");
  });

  it("uses the latest correction without mutating history", () => {
    const measurements = [
      { id: "1", type: "MASH_PH", value: "5.42" },
      { id: "2", type: "MASH_PH", value: "5.40", correction_of_id: "1" },
    ] as Measurement[];
    expect(latestMeasurement(measurements, "MASH_PH")?.value).toBe("5.40");
    expect(measurements[0].value).toBe("5.42");
  });

  it("parses voice transcripts as uncommitted drafts", () => {
    const draft = parseVoiceProposal("five point two pH");
    expect(draft).toEqual({
      transcript: "five point two pH",
      field: "MASH_PH",
      value: "5.2",
      unit: "pH",
      action: "record_measurement",
      committed: "false",
    });
    expect(parseVoiceProposal("fifty two pH")?.value).toBe("52");
  });

  it("keeps planned and actual values separate when calculating display variance", () => {
    expect(variance("1.048", "1.050")).toBe("-0.002");
    expect(variance("5.42", "5.30")).toBe("+0.12");
  });

  it("creates operation ids without requiring a secure crypto context", () => {
    const id = newOperationId();
    expect(id.length).toBeGreaterThan(8);
    expect(newOperationId()).not.toBe(id);
  });

  it("sends operation identity and expected revision on session commands", () => {
    const body = sessionCommand(4, { reason: "timer extension" });
    expect(body.expected_revision).toBe(4);
    expect(String(body.operation_id).length).toBeGreaterThan(8);
    expect(body.reason).toBe("timer extension");
  });

  it("includes observed measurement context instead of inventing method later", () => {
    const body = measurementCommand("MASH_PH", "5.32", {
      method: "METER",
      sample_temperature_c: "65.00",
      temperature_compensated: true,
    });
    expect(body.method).toBe("METER");
    expect(body.sample_temperature_c).toBe("65.00");
    expect(body.temperature_compensated).toBe(true);
    expect(body.operation_id).toBeTruthy();
  });
});
