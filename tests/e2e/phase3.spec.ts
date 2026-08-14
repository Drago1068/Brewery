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

async function signInAndStartMash(page: Page, recipeName: string) {
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
  await expect(page.getByTestId("mash-timer")).toBeVisible({ timeout: 15_000 });
}

test("voice draft cannot commit fifty-two as mash pH", async ({ page }) => {
  await signInAndStartMash(page, `Voice Gate ${Date.now()}`);
  await page.getByPlaceholder("five point two pH").fill("fifty two pH");
  await page.getByRole("button", { name: "Parse transcript" }).click();
  await expect(page.getByText("Proposed MASH_PH:")).toBeVisible();
  await expect(page.getByText("52 pH")).toBeVisible();
  await page.getByRole("button", { name: "Confirm voice measurement" }).click();
  await expect(page.locator(".alert.error")).toBeVisible();
  await expect(page.getByLabel("pH reading")).toBeVisible();
});

test("pause, resume, refresh recovery, and journal remain authoritative", async ({ page }) => {
  await signInAndStartMash(page, `Recovery ${Date.now()}`);
  await page.getByRole("button", { name: "Pause session" }).click();
  await expect(page.locator(".brew-topbar .status")).toHaveText("PAUSED");
  await page.reload();
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  await expect(page.locator(".brew-topbar .status")).toHaveText("PAUSED");
  await page.getByRole("button", { name: "Resume session" }).click();
  await expect(page.locator(".brew-topbar .status")).toHaveText("ACTIVE");
  await page.getByLabel("pH reading").fill("5.42");
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
  await expect(page.locator(".measurement-card.done strong").filter({ hasText: "1.048" })).toBeVisible();
  await page.getByRole("button", { name: "Complete Mash", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mash performance" })).toBeVisible();
  await expect(page.locator(".performance").getByText("5.420", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
});

test("phone viewport keeps mash timer and measurement controls usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAndStartMash(page, `Phone Brew ${Date.now()}`);
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  await expect(page.getByLabel("pH reading")).toBeVisible();
  await expect(page.getByRole("button", { name: "Record pH" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause session" })).toBeVisible();
});

test("tablet viewport and keyboard focus remain usable", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await signInAndStartMash(page, `Tablet Brew ${Date.now()}`);
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  const record = page.getByRole("button", { name: "Record pH" });
  await record.focus();
  await expect(record).toBeFocused();
  await expect(page.getByLabel("Gravity reading")).toBeVisible();
  await expect(page.getByLabel("Transcript")).toBeVisible();
});

test("canonical brew-day controls: three timers, reminders, note, refresh, journal", async ({ page }) => {
  await signInAndStartMash(page, `Canonical Mash ${Date.now()}`);
  await page.getByLabel("Auxiliary timer name").fill("Hop check");
  await page.getByLabel("Duration (seconds)").fill("120");
  await Promise.all([
    page.waitForResponse(
      (response) => response.url().includes("/timers") && response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Start auxiliary timer" }).click(),
  ]);
  await page.getByLabel("Auxiliary timer name").fill("Iodine check");
  await Promise.all([
    page.waitForResponse(
      (response) => response.url().includes("/timers") && response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Start auxiliary timer" }).click(),
  ]);
  await expect(page.getByRole("list", { name: "Active timers" }).getByRole("listitem")).toHaveCount(3, {
    timeout: 15_000,
  });
  const due = page.getByRole("button", { name: "Acknowledge" }).first();
  if (await due.isVisible().catch(() => false)) {
    await due.click();
  }
  await page.getByLabel("pH reading").fill("5.30");
  await page.getByRole("button", { name: "Record pH" }).click();
  await page.getByLabel("Gravity reading").fill("1.050");
  await page.getByRole("button", { name: "Record gravity" }).click();
  await page.getByLabel("Brew-day note").fill("Canonical note for journal evidence");
  await page.getByRole("button", { name: "Add note" }).click();
  await page.reload();
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  await expect(page.getByText("Canonical note for journal evidence")).toBeVisible();
  await page.getByRole("button", { name: "Complete Mash", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Stage progress" })).toBeVisible();
});
