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
  const aborted = await page.request.post(`/api/v1/brew-sessions/${body.id}/abort`, {
    data: { reason: "Clearing prior E2E brew session before the next scenario" },
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
  await page.getByLabel("Recipe name").fill(recipeName);
  await page.getByLabel("Duration (min)").fill("1");
  await page.getByRole("button", { name: "Create recipe v1" }).click();
  const recipeCard = page.getByRole("heading", { name: recipeName }).locator("..");
  await expect(recipeCard).toBeVisible();
  await recipeCard.getByRole("button", { name: "Start brew session" }).click();
  await expect(page.getByRole("heading", { name: "Ready to start Mash" })).toBeVisible();
  await page.getByRole("button", { name: "Start Mash" }).click();
  await expect(page.getByTestId("mash-timer")).toBeVisible();
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
  await expect(page.getByText("PAUSED", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  await expect(page.getByText("PAUSED", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Resume session" }).click();
  await expect(page.getByText("ACTIVE", { exact: true })).toBeVisible();
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
  await page.getByRole("button", { name: "Complete Mash" }).click();
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
  await expect(page.getByRole("timer")).toBeVisible();
  const record = page.getByRole("button", { name: "Record pH" });
  await record.focus();
  await expect(record).toBeFocused();
  await expect(page.getByLabel("Gravity reading")).toBeVisible();
  await expect(page.getByLabel("Transcript")).toBeVisible();
});
