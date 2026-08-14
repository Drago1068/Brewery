import { expect, test, type Page } from "@playwright/test";

async function clearActiveBrew(page: Page) {
  const origin = process.env.BASE_URL ?? "http://web:3000";
  const csrf =
    (await page.evaluate(() => sessionStorage.getItem("csrf_token"))) ||
    (await page.request.get("/api/v1/auth/csrf", { headers: { Origin: origin } }).then(async (r) =>
      r.ok() ? ((await r.json()).csrf_token as string) : "",
    ));
  if (!csrf) throw new Error("Missing CSRF token while clearing active brew");
  const active = await page.request.get("/api/v1/brew-sessions/active", {
    headers: { Origin: origin },
  });
  if (!active.ok()) throw new Error(`Active brew lookup failed: ${active.status()}`);
  const body = await active.json();
  if (!body?.id) return;
  const details = await page.request.get(`/api/v1/brew-sessions/${body.id}`, {
    headers: { Origin: origin },
  });
  const revision = details.ok() ? ((await details.json()).revision as number) : 1;
  const aborted = await page.request.post(`/api/v1/brew-sessions/${body.id}/abort`, {
    data: {
      reason: "Clearing prior E2E brew session before the next scenario",
      expected_revision: revision,
      operation_id: `e2e-abort-${Date.now()}`,
    },
    headers: { Origin: origin, "X-CSRF-Token": csrf, "Content-Type": "application/json" },
  });
  if (!aborted.ok()) {
    throw new Error(`Abort failed: ${aborted.status()} ${await aborted.text()}`);
  }
  await page.reload();
  await expect(page.getByRole("button", { name: "Start brew session" }).first()).toBeVisible({
    timeout: 15_000,
  });
}

function seconds(value: string): number {
  const [hours, minutes, secs] = value.split(":").map(Number);
  return hours * 3600 + minutes * 60 + secs;
}

test("complete Phase 1A workflow and recover the Mash timer after refresh", async ({ page }) => {
  const recipeName = `Architecture Ale ${Date.now()}`;
  await page.goto("/login");
  await page.getByLabel("Username").fill(process.env.E2E_USERNAME ?? "brewer");
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Plan once. Brew with confidence." })).toBeVisible();
  await clearActiveBrew(page);

  const origin = process.env.BASE_URL ?? "http://web:3000";
  const csrf =
    (await page.evaluate(() => sessionStorage.getItem("csrf_token"))) ||
    (await page.request.get("/api/v1/auth/csrf", { headers: { Origin: origin } }).then(async (r) =>
      r.ok() ? ((await r.json()).csrf_token as string) : "",
    ));
  const created = await page.request.post("/api/v1/recipes", {
    data: {
      name: recipeName,
      target_mash_temperature: "152",
      planned_mash_duration_minutes: 1,
      target_mash_ph: "5.30",
      mash_ph_tolerance: "0.05",
      target_mash_gravity: "1.050",
      mash_gravity_tolerance: "0.003",
    },
    headers: { Origin: origin, "X-CSRF-Token": csrf, "Content-Type": "application/json" },
  });
  if (!created.ok()) {
    throw new Error(`Recipe create failed: ${created.status()} ${await created.text()}`);
  }
  await page.goto("/");
  const recipeCard = page.getByRole("heading", { name: recipeName }).locator("..");
  await expect(recipeCard).toBeVisible({ timeout: 20_000 });
  await recipeCard.getByRole("button", { name: "Start brew session" }).click();

  await expect(page.getByRole("heading", { name: "Ready to start Mash" })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Start Mash" }).click();
  const requiredActions = page.getByRole("region", { name: "Required actions" });
  await expect(requiredActions.getByText("Measure Mash pH", { exact: true })).toBeVisible();
  await expect(requiredActions.getByText("Measure Mash Gravity", { exact: true })).toBeVisible();

  const timer = page.getByTestId("mash-timer");
  const before = seconds(await timer.innerText());
  await page.waitForTimeout(1_200);
  await page.reload();
  await expect(timer).toBeVisible();
  const after = seconds(await timer.innerText());
  expect(after).toBeGreaterThanOrEqual(before + 1);

  await page.getByLabel("pH reading").fill("5.42");
  await page.getByLabel("Instrument").first().fill("Calibrated meter");
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/measurements") && response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Record pH" }).click(),
  ]);
  await expect(page.locator(".measurement-card.done strong").filter({ hasText: "5.420" })).toBeVisible();

  await page.getByLabel("Gravity reading").fill("1.048");
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes("/measurements") && response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Record gravity" }).click(),
  ]);
  await Promise.all([
    page.waitForResponse(
      (response) => response.url().includes("/complete") && response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Complete Mash", exact: true }).click(),
  ]);

  await expect(page.locator(".brew-topbar .status")).toHaveText("COMPLETED", { timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "Mash performance" })).toBeVisible();
  await expect(page.locator(".performance").getByText("5.420", { exact: true })).toBeVisible();
  await expect(page.locator(".performance").getByText("1.048 SG", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
  await expect(page.getByText("Mash completed")).toBeVisible();
});
