/**
 * Phase 4 Candidate 2 — Playwright final-acceptance suite (verification-only).
 * Exercises Candidate 2 browser-visible Phase 4 flows. Does not invent frontend authority.
 */
import { expect, test, type Page } from "@playwright/test";

import {
  assertErrorAssociation,
  assertFermentA11y,
  clickAndWaitFerment,
  csrfHeaders,
  e2eOrigin,
  postJson,
  seedActiveFermentation,
  signIn,
  waitForFermentIdle,
} from "./helpers";

async function openWorksheet(page: Page, fermentationId: string) {
  await page.goto(`/ferment/${fermentationId}`);
  await expect(page.getByRole("status", { name: "Session status" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("ferment-status")).toHaveText("ACTIVE");
  await waitForFermentIdle(page);
}

test.describe("Phase 4 final acceptance — Playwright", () => {
  test("FA-PW-01 lifecycle measurement correction reload", async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    const seeded = await seedActiveFermentation(page, `P4 FA PW ${Date.now()}`);
    await openWorksheet(page, seeded.fermentationSessionId);

    await page.getByLabel("Gravity reading").fill("1.024");
    await page.getByLabel("Measurement note").fill("FA measurement entry");
    await clickAndWaitFerment(
      page,
      page.getByRole("button", { name: "Record gravity" }),
      "/measurements",
    );
    await expect(page.getByText(/FA measurement entry/)).toBeVisible();

    const statusBefore = await page.getByTestId("ferment-status").innerText();
    await page.reload();
    await expect(page.getByTestId("ferment-status")).toHaveText(statusBefore, { timeout: 20_000 });
    await expect(page.getByText(/FA measurement entry/)).toBeVisible();
    await waitForFermentIdle(page);
  });

  test("FA-PW-02 readiness handoff happy path", async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    const seeded = await seedActiveFermentation(page, `P4 FA Hand ${Date.now()}`);
    await openWorksheet(page, seeded.fermentationSessionId);

    await page.getByLabel("Gravity reading").fill("1.021");
    await page.getByLabel("Measurement note").fill("FA handoff gravity");
    await clickAndWaitFerment(
      page,
      page.getByRole("button", { name: "Record gravity" }),
      "/measurements",
    );

    await page.getByLabel("Override fermentation completion eligibility").check();
    await page.getByLabel("Override reason").fill("FA eligibility override for handoff path");
    await clickAndWaitFerment(
      page,
      page.getByTestId("complete-fermentation"),
      "/commands/complete-fermentation",
    );
    await expect(page.getByTestId("ferment-status")).toHaveText("FERMENTATION_COMPLETE");

    await clickAndWaitFerment(page, page.getByTestId("skip-conditioning"), "/commands/skip-conditioning");
    await expect(page.getByTestId("ferment-status")).toHaveText("CONDITIONING_COMPLETE");

    await page.getByLabel("Override packaging readiness R3").check();
    await page
      .getByLabel("Readiness override reason")
      .fill("FA R3 override when OG pin is UNKNOWN on legacy brew seed");
    await clickAndWaitFerment(
      page,
      page.getByTestId("assess-readiness"),
      "/commands/assess-packaging-readiness",
    );
    await expect(page.getByTestId("ferment-status")).toHaveText("COMPLETION_ASSESSED");
    await clickAndWaitFerment(
      page,
      page.getByTestId("record-handoff"),
      "/commands/record-packaging-readiness-handoff",
    );
    await expect(page.getByTestId("ferment-status")).toHaveText("HANDOFF_READY");
    await expect(page.getByText(/No packaging execution is available/i)).toBeVisible();
  });

  test("FA-PW-03 accessibility keyboard 360px", async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 360, height: 740 });
    await signIn(page);
    const seeded = await seedActiveFermentation(page, `P4 FA A11y ${Date.now()}`);
    await openWorksheet(page, seeded.fermentationSessionId);
    await assertFermentA11y(page, { mobile: true });

    await page.getByLabel("Gravity reading").fill("1.022");
    await page.getByLabel("Measurement note").fill("FA 360 keyboard note");
    await page.getByRole("button", { name: "Record gravity" }).focus();
    await expect(page.getByRole("button", { name: "Record gravity" })).toBeFocused();
    await clickAndWaitFerment(
      page,
      page.getByRole("button", { name: "Record gravity" }),
      "/measurements",
    );
    await expect(page.getByText(/FA 360 keyboard note/)).toBeVisible();
  });

  test("FA-PW-04 stale revision error association", async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    const seeded = await seedActiveFermentation(page, `P4 FA Stale ${Date.now()}`);
    await openWorksheet(page, seeded.fermentationSessionId);

    const origin = e2eOrigin();
    const headers = await csrfHeaders(page, origin);
    const detail = await page.request.get(
      `/api/v1/fermentation-sessions/${seeded.fermentationSessionId}`,
      { headers: { Origin: origin } },
    );
    expect(detail.ok()).toBeTruthy();
    const revision = (await detail.json()).revision as number;
    await postJson(
      page.request,
      `/api/v1/fermentation-sessions/${seeded.fermentationSessionId}/commands/pause`,
      { operation_id: `fa-stale-pause-${Date.now()}`, expected_revision: revision },
      headers,
    );

    await page.getByLabel("Override fermentation completion eligibility").check();
    await page.getByLabel("Override reason").fill("Stale UI attempt after authoritative pause");
    const pending = page.waitForResponse(
      (response) =>
        response.url().includes("/commands/complete-fermentation") &&
        response.request().method() === "POST",
      { timeout: 20_000 },
    );
    await page.getByTestId("complete-fermentation").click();
    const response = await pending;
    expect([409, 422]).toContain(response.status());
    await expect(page.locator("#ferment-session-error")).toBeVisible();
    await assertErrorAssociation(page);
    await expect(page.getByTestId("ferment-status")).toHaveText("PAUSED");
  });

  test("FA-PW-05 foreign session not disclosed", async ({ page }) => {
    test.setTimeout(120_000);
    await signIn(page);
    await page.goto("/ferment/00000000-0000-4000-8000-000000000099");
    await expect(page.locator("#ferment-session-error")).toContainText(/not found|unavailable/i);
    await expect(page.getByTestId("ferment-status")).toHaveCount(0);
  });

  test("FA-PW-06 browser worksheet usable timing sample", async ({ page }) => {
    test.setTimeout(180_000);
    await signIn(page);
    const seeded = await seedActiveFermentation(page, `P4 FA Perf ${Date.now()}`);
    const started = Date.now();
    await openWorksheet(page, seeded.fermentationSessionId);
    const elapsed = Date.now() - started;
    // Spec §37 browser worksheet usable state p95 ≤ 2500 ms (single sample evidence row).
    expect(elapsed).toBeLessThanOrEqual(2500);
  });
});
