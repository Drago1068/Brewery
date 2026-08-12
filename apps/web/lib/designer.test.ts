import { describe, expect, it } from "vitest";

import { defaultStage, displayEstimate, makeDraftLine } from "./designer";

describe("recipe designer helpers", () => {
  it("assigns process-aware stages and canonical units", () => {
    expect(defaultStage("FERMENTABLE")).toBe("MASH");
    expect(defaultStage("HOP")).toBe("BOIL");
    expect(defaultStage("YEAST")).toBe("FERMENTATION");
    expect(
      makeDraftLine(
        { id: "hop-1", name: "Cascade", category: "HOP", canonical_unit: "g" },
        "25",
      ),
    ).toEqual({
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
});
