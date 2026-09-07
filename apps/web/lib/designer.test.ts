import { describe, expect, it } from "vitest";

import {
  addMashStep,
  applyLinePatch,
  defaultMashStep,
  defaultStage,
  displayEstimate,
  editMashStep,
  makeDraftLine,
  mashStepError,
  orderMashSteps,
  parsePositiveAmount,
  parseTimingMinutes,
  removeMashStep,
  stageAllowsTiming,
  stageRequiresTiming,
  toProcessSteps,
  type Ingredient,
} from "./designer";

const hop: Ingredient = { id: "hop-1", name: "Cascade", category: "HOP", canonical_unit: "g" };
const malt: Ingredient = {
  id: "malt-1",
  name: "Pale Malt",
  category: "FERMENTABLE",
  canonical_unit: "g",
};
const yeast: Ingredient = {
  id: "yeast-1",
  name: "US-05",
  category: "YEAST",
  canonical_unit: "each",
};

describe("recipe designer helpers", () => {
  it("assigns process-aware stages and canonical units", () => {
    expect(defaultStage("FERMENTABLE")).toBe("MASH");
    expect(defaultStage("HOP")).toBe("BOIL");
    expect(defaultStage("YEAST")).toBe("FERMENTATION");
    expect(makeDraftLine(hop, "25")).toEqual({
      ingredient_id: "hop-1",
      amount: "25",
      unit: "g",
      use_stage: "BOIL",
      timing_minutes: 60,
    });
  });

  it("does not fabricate missing estimates", () => {
    expect(displayEstimate(undefined, 3)).toBe("Not calculated");
    expect(displayEstimate("1.05267", 3)).toBe("1.053");
  });

  it("edits an existing addition amount", () => {
    const line = makeDraftLine(malt, "5000");
    const result = applyLinePatch(line, malt, { amount: "4500.25" });
    expect(result.error).toBeUndefined();
    expect(result.line.amount).toBe("4500.25");
    expect(result.line.unit).toBe("g");
  });

  it("rejects non-positive and non-decimal amounts", () => {
    const line = makeDraftLine(malt, "5000");
    expect(parsePositiveAmount("0")).toBeUndefined();
    expect(applyLinePatch(line, malt, { amount: "-1" }).error).toMatch(/positive/);
    expect(applyLinePatch(line, malt, { amount: "1e2" }).error).toMatch(/positive/);
    expect(applyLinePatch(line, malt, { amount: "1.00001" }).error).toMatch(/positive/);
  });

  it("accepts a valid canonical unit and rejects dimension-mismatched units", () => {
    const line = makeDraftLine(malt, "5000");
    expect(applyLinePatch(line, malt, { unit: "g" }).error).toBeUndefined();
    expect(applyLinePatch(line, malt, { unit: "L" }).error).toMatch(/canonical unit/);
    expect(applyLinePatch(line, malt, { unit: "oz" }).error).toMatch(/canonical/);
  });

  it("changes stage to an allowed value and rejects unknown stages", () => {
    const line = makeDraftLine(hop, "40");
    const whirlpool = applyLinePatch(line, hop, { use_stage: "WHIRLPOOL", timing_minutes: 10 });
    expect(whirlpool.error).toBeUndefined();
    expect(whirlpool.line.use_stage).toBe("WHIRLPOOL");
    expect(whirlpool.line.timing_minutes).toBe(10);
    expect(applyLinePatch(line, hop, { use_stage: "LATER" }).error).toMatch(/stage/);
  });

  it("changes timing and rejects negative or invalid timing", () => {
    const line = makeDraftLine(hop, "40");
    expect(applyLinePatch(line, hop, { timing_minutes: 15 }).line.timing_minutes).toBe(15);
    expect(applyLinePatch(line, hop, { timing_minutes: -1 }).error).toMatch(/Timing/);
    expect(parseTimingMinutes("-5")).toBeUndefined();
  });

  it("does not require fabricated timing on non-timed stages", () => {
    expect(stageRequiresTiming("FERMENTATION")).toBe(false);
    expect(stageAllowsTiming("FERMENTATION")).toBe(false);
    const line = makeDraftLine(yeast, "1");
    expect(line.timing_minutes).toBeUndefined();
    const moved = applyLinePatch(line, yeast, { use_stage: "PACKAGING" });
    expect(moved.error).toBeUndefined();
    expect(moved.line.timing_minutes).toBeUndefined();
  });

  it("adds, edits, removes, and orders mash steps deterministically", () => {
    const protein = { name: "Protein rest", duration_minutes: "20", temperature_c: "52" };
    let steps = addMashStep([defaultMashStep()], protein);
    expect(steps).toHaveLength(2);
    steps = editMashStep(steps, 0, { duration_minutes: "45", temperature_c: "67" });
    expect(steps[0]).toEqual({
      name: "Saccharification",
      duration_minutes: "45",
      temperature_c: "67",
    });
    steps = orderMashSteps(steps, 1, 0);
    expect(steps.map((step) => step.name)).toEqual(["Protein rest", "Saccharification"]);
    const payloads = toProcessSteps(steps, "60");
    expect(payloads.error).toBeUndefined();
    expect(payloads.steps?.map((step) => [step.step_type, step.sequence, step.name])).toEqual([
      ["MASH", 1, "Protein rest"],
      ["MASH", 2, "Saccharification"],
      ["BOIL", 3, "Boil"],
    ]);
    steps = removeMashStep(steps, 0);
    expect(steps.map((step) => step.name)).toEqual(["Saccharification"]);
    expect(mashStepError({ name: "", duration_minutes: "10", temperature_c: "65" })).toMatch(/name/);
  });
});
