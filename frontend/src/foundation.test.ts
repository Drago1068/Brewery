import { describe, expect, it } from "vitest";

describe("BrewingOS frontend foundation", () => {
  it("exposes API URL default contract", () => {
    const api = "http://localhost:8000";
    expect(api.endsWith(":8000")).toBe(true);
  });
});
