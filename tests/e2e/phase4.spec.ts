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

async function completeHappyPathToHandoff(page: Page) {
  await expect(page.getByTestId("ferment-status")).toHaveText("ACTIVE");

  await page.getByLabel("Gravity reading").fill("1.021");
  await page.getByLabel("Measurement note").fill("Happy-path gravity leaf for override");
  await clickAndWaitFerment(page, page.getByRole("button", { name: "Record gravity" }), "/measurements");
  await expect(page.getByText(/Happy-path gravity leaf for override/)).toBeVisible();

  const override = page.getByLabel("Override fermentation completion eligibility");
  await override.check();
  await page.getByLabel("Override reason").fill("E2E eligibility override for canonical happy path");
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
    .fill("E2E R3 override when OG pin is UNKNOWN on legacy brew seed");
  await clickAndWaitFerment(
    page,
    page.getByTestId("assess-readiness"),
    "/commands/assess-packaging-readiness",
  );
  await expect(page.getByTestId("ferment-status")).toHaveText("COMPLETION_ASSESSED");
  const assessmentId = (await page.getByTestId("assessment-id").innerText()).trim();
  expect(assessmentId).not.toBe("—");
  expect(assessmentId.length).toBeGreaterThan(8);

  await clickAndWaitFerment(
    page,
    page.getByTestId("record-handoff"),
    "/commands/record-packaging-readiness-handoff",
  );
  await expect(page.getByTestId("ferment-status")).toHaveText("HANDOFF_READY");
  const handoffId = (await page.getByTestId("handoff-id").innerText()).trim();
  expect(handoffId).not.toBe("—");
  await expect(page.getByTestId("handoff-status")).toContainText(/READY/);
  return { assessmentId, handoffId };
}

test("P4-AC-050 canonical UI happy path ACTIVE through handoff", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  const seeded = await seedActiveFermentation(page, `P4 Happy ${Date.now()}`);
  await openWorksheet(page, seeded.fermentationSessionId);
  const ids = await completeHappyPathToHandoff(page);
  await expect(page.getByTestId("assessment-id")).toHaveText(ids.assessmentId);
  await expect(page.getByTestId("handoff-id")).toHaveText(ids.handoffId);
  await expect(page.getByText(/No packaging execution is available/i)).toBeVisible();
});

test("P4-AC-045 / P4-FR-082 keyboard and 360px measurement reminder state note flows", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 360, height: 740 });
  await signIn(page);
  const seeded = await seedActiveFermentation(page, `P4 A11y ${Date.now()}`);
  await openWorksheet(page, seeded.fermentationSessionId);
  await assertFermentA11y(page, { mobile: true });

  const reminders = page.getByRole("region", { name: "Required actions" });
  if (await reminders.isVisible().catch(() => false)) {
    const ack = reminders.getByRole("button", { name: "Acknowledge" }).first();
    await ack.focus();
    await expect(ack).toBeFocused();
    await clickAndWaitFerment(page, ack, "/reminders/");
  }

  await page.getByLabel("Gravity reading").fill("1.022");
  await page.getByLabel("Measurement note").fill("360px keyboard note capture");
  await page.getByRole("button", { name: "Record gravity" }).focus();
  await expect(page.getByRole("button", { name: "Record gravity" })).toBeFocused();
  await clickAndWaitFerment(page, page.getByRole("button", { name: "Record gravity" }), "/measurements");
  await expect(page.getByText(/360px keyboard note capture/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Lifecycle stages" })).toBeVisible();
  await expect(page.getByTestId("ferment-status")).toBeVisible();
});

test("P4-FR-082 stale revision and backend denial remain visible", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page);
  const seeded = await seedActiveFermentation(page, `P4 Stale ${Date.now()}`);
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
    { operation_id: `e2e-stale-pause-${Date.now()}`, expected_revision: revision },
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

test("P4 security: foreign fermentation id is not disclosed", async ({ page }) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.goto("/ferment/00000000-0000-4000-8000-000000000099");
  await expect(page.locator("#ferment-session-error")).toContainText(/not found|unavailable/i);
  await expect(page.getByTestId("ferment-status")).toHaveCount(0);
});
