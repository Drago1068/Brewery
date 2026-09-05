import { expect, type APIRequestContext, type Locator, type Page, type Response } from "@playwright/test";

export function e2eOrigin(): string {
  return process.env.BASE_URL ?? "http://web:3000";
}

export function isPostTo(urlPart: string) {
  return (response: Response) =>
    response.url().includes(urlPart) && response.request().method() === "POST";
}

export async function csrfHeaders(page: Page, origin = e2eOrigin()) {
  const csrf =
    (await page.evaluate(() => sessionStorage.getItem("csrf_token"))) ||
    (await page.request
      .get("/api/v1/auth/csrf", { headers: { Origin: origin } })
      .then(async (r) => (r.ok() ? ((await r.json()).csrf_token as string) : "")));
  if (!csrf) throw new Error("Missing CSRF token");
  return { Origin: origin, "X-CSRF-Token": csrf, "Content-Type": "application/json" };
}

export async function postJson(
  request: APIRequestContext,
  path: string,
  data: unknown,
  headers: Record<string, string>,
) {
  const response = await request.post(path, { data, headers });
  if (!response.ok()) {
    throw new Error(`${path} failed: ${response.status()} ${await response.text()}`);
  }
  return response.json();
}

export async function clickAndWait(page: Page, button: Locator, urlPart: string, options?: { allowConflict?: boolean }) {
  await expect(button).toBeEnabled({ timeout: 20_000 });
  const pending = page.waitForResponse(isPostTo(urlPart), { timeout: 20_000 });
  await button.click();
  const response = await pending;
  if (options?.allowConflict && response.status() === 409) {
    await waitForBrewIdle(page);
    return response;
  }
  if (!response.ok()) {
    throw new Error(`${urlPart} failed: ${response.status()} ${await response.text()}`);
  }
  await waitForBrewIdle(page);
  return response;
}

export async function waitForBrewIdle(page: Page) {
  const control = page
    .getByRole("button", {
      name: /^(Pause session|Resume session|Start Mash|Complete Mash|Complete brew session|Start auxiliary timer)$/,
    })
    .or(page.getByTestId("start-current-stage"))
    .first();
  if (await control.isVisible().catch(() => false)) {
    await expect(control).toBeEnabled({ timeout: 20_000 });
  }
}

export async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill(process.env.E2E_USERNAME ?? "brewer");
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Plan once. Brew with confidence." })).toBeVisible({
    timeout: 20_000,
  });
}

export async function clearActiveBrew(page: Page) {
  const origin = e2eOrigin();
  const headers = await csrfHeaders(page, origin);
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
    headers,
  });
  if (!aborted.ok()) {
    throw new Error(`Abort failed: ${aborted.status()} ${await aborted.text()}`);
  }
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Start brew session" }).first()).toBeVisible({
    timeout: 15_000,
  });
}

export async function createLegacyRecipe(page: Page, name: string) {
  const origin = e2eOrigin();
  const headers = await csrfHeaders(page, origin);
  return postJson(
    page.request,
    "/api/v1/recipes",
    {
      name,
      target_mash_temperature: "152",
      planned_mash_duration_minutes: 1,
      target_mash_ph: "5.30",
      mash_ph_tolerance: "0.05",
      target_mash_gravity: "1.050",
      mash_gravity_tolerance: "0.003",
    },
    headers,
  );
}

export async function startBrewFromRecipeCard(page: Page, recipeName: string) {
  await page.goto("/");
  const recipeCard = page.getByRole("heading", { name: recipeName }).locator("..");
  await expect(recipeCard).toBeVisible({ timeout: 20_000 });
  await recipeCard.getByRole("button", { name: "Start brew session" }).click();
  await expect(page.getByRole("heading", { name: "Stage progress" })).toBeVisible({
    timeout: 20_000,
  });
}

/** Advance optional/prior stages until Mash is started and the mash timer is visible. */
export async function reachAndStartMash(page: Page) {
  for (let step = 0; step < 25; step += 1) {
    const mashTimer = page.getByTestId("mash-timer");
    if (await mashTimer.isVisible().catch(() => false)) {
      return;
    }

    const startMash = page.getByRole("button", { name: "Start Mash", exact: true });
    if (await startMash.isVisible().catch(() => false)) {
      await clickAndWait(page, startMash, "/mash/start");
      await expect(mashTimer).toBeVisible({ timeout: 20_000 });
      return;
    }

    const skipOptional = page.getByRole("button", { name: /^Skip / }).first();
    const startCurrent = page.getByTestId("start-current-stage");
    const betweenStages = !(await page.getByRole("button", { name: "Pause session" }).isVisible().catch(() => false));
    if (
      betweenStages &&
      (await skipOptional.isVisible().catch(() => false)) &&
      /Skip (MILLING|LAUTER_SPARGE)/.test((await skipOptional.innerText().catch(() => "")) || "")
    ) {
      await clickAndWait(page, skipOptional, "/skip");
      continue;
    }

    if (await startCurrent.isVisible().catch(() => false)) {
      await clickAndWait(page, startCurrent, "/stages/");
      await completePendingChecklists(page);
      await recordVisibleStageMeasurements(page);
      await executeVisibleAdditions(page, { late: false, correct: false });
      const completeStage = page
        .getByRole("button", { name: /^Complete / })
        .filter({ hasNotText: "brew session" })
        .filter({ hasNotText: "Mash" })
        .first();
      if (await completeStage.isVisible().catch(() => false)) {
        await clickAndWait(page, completeStage, "/complete");
      }
      continue;
    }

    await page.waitForTimeout(400);
  }

  throw new Error(
    "Stuck before Mash: Start Mash / mash-timer not reached within 25 advancement steps",
  );
}

export async function recordMashPh(page: Page, value: string) {
  const input = page.getByLabel("pH reading");
  if (!(await input.isVisible().catch(() => false))) {
    await expect(page.locator(".measurement-card.done").filter({ hasText: "Mash pH" })).toBeVisible();
    return;
  }
  const card = page.locator(".measurement-card").filter({ has: input });
  await input.fill(value);
  await card.getByLabel("pH method").selectOption("METER");
  await card.getByLabel("Sample temperature (°C)").fill("65.00");
  const instrument = card.getByLabel("Instrument");
  if (await instrument.isVisible().catch(() => false)) {
    await instrument.fill("Calibrated meter");
  }
  await clickAndWait(page, card.getByRole("button", { name: "Record pH" }), "/measurements");
  await expect(page.locator(".measurement-card.done").filter({ hasText: "Mash pH" })).toBeVisible();
}

export async function recordMashGravity(page: Page, value: string) {
  const input = page.getByLabel("Gravity reading");
  if (!(await input.isVisible().catch(() => false))) {
    await expect(page.locator(".measurement-card.done").filter({ hasText: "Mash gravity" })).toBeVisible();
    return;
  }
  const card = page.locator(".measurement-card").filter({ has: input });
  await input.fill(value);
  await card.getByLabel("Gravity method").selectOption("HYDROMETER");
  await card.getByLabel("Sample temperature (°C)").fill("20.00");
  await clickAndWait(page, card.getByRole("button", { name: "Record gravity" }), "/measurements");
  await expect(page.locator(".measurement-card.done").filter({ hasText: "Mash gravity" })).toBeVisible();
}

const STAGE_MEASUREMENTS: Record<string, Array<[string, string]>> = {
  MASH_IN: [["MASH_IN_TEMPERATURE", "67"]],
  MASH: [
    ["MASH_REST_TEMPERATURE", "67"],
    ["MASH_PH", "5.30"],
    ["POST_MASH_GRAVITY", "1.050"],
  ],
  PRE_BOIL: [
    ["PRE_BOIL_GRAVITY", "1.052"],
    ["PRE_BOIL_VOLUME", "20"],
  ],
  CHILL: [["KNOCKOUT_TEMPERATURE", "18"]],
  TRANSFER: [["KNOCKOUT_VOLUME", "19"]],
  YEAST_PITCH: [["PITCH_TEMPERATURE", "18"]],
};

export async function recordMeasurement(page: Page, type: string, value: string) {
  if (type === "MASH_PH") {
    if (await page.getByLabel("pH reading").isVisible().catch(() => false)) {
      await recordMashPh(page, value);
    }
    return;
  }
  if (type === "MASH_GRAVITY" || type === "POST_MASH_GRAVITY") {
    if (await page.getByLabel("Gravity reading").isVisible().catch(() => false)) {
      await recordMashGravity(page, value);
      return;
    }
    if (await page.locator(".measurement-card.done").filter({ hasText: "Mash gravity" }).isVisible().catch(() => false)) {
      return;
    }
  }

  const form = page.getByRole("region", { name: "Measurements" });
  await expect(form).toBeVisible({ timeout: 15_000 });
  await form.getByLabel("Measurement type").selectOption(type);
  await form.getByLabel("Measurement value").fill(value);
  const method = form.getByLabel("Measurement method");
  if (await method.isVisible().catch(() => false)) {
    const options = await method.locator("option").allTextContents();
    if (options.length) await method.selectOption({ index: 0 });
  }
  const sampleTemp = form.getByLabel("Sample temperature (°C)");
  if (await sampleTemp.isVisible().catch(() => false)) {
    await sampleTemp.fill(type === "MASH_PH" || type.endsWith("_PH") ? "65.00" : "20.00");
  }
  const vessel = form.getByLabel("Vessel");
  if (await vessel.isVisible().catch(() => false)) {
    const current = await vessel.inputValue();
    if (!current) {
      await vessel.fill(type.startsWith("KNOCKOUT") ? "RECEIVING" : "KETTLE");
    }
  }
  const response = await clickAndWait(
    page,
    form.getByRole("button", { name: "Record measurement" }),
    "/measurements",
    { allowConflict: true },
  );
  if (!response.ok() && response.status() !== 409) {
    throw new Error(`/measurements failed: ${response.status()} ${await response.text()}`);
  }
}

export async function recordVisibleStageMeasurements(page: Page, stageKey?: string) {
  const key = (stageKey ?? (await currentStageKey(page))).replaceAll(" ", "_").toUpperCase();
  const measurements = STAGE_MEASUREMENTS[key] ?? [];
  for (const [type, value] of measurements) {
    await recordMeasurement(page, type, value);
  }
  if (!measurements.length) {
    await satisfyActiveStageMeasurements(page);
  }
}

export async function satisfyActiveStageMeasurements(page: Page) {
  const sessionId = page.url().split("/brew/")[1]?.split("?")[0];
  if (!sessionId) return;
  const details = await page.request.get(`/api/v1/brew-sessions/${sessionId}`);
  if (!details.ok()) return;
  const body = await details.json();
  const activeId = body.current_stage?.id ?? body.mash?.id;
  const values: Record<string, string> = {
    MASH_IN_TEMPERATURE: "67",
    MASH_REST_TEMPERATURE: "67",
    MASH_PH: "5.30",
    POST_MASH_GRAVITY: "1.050",
    MASH_GRAVITY: "1.050",
    PRE_BOIL_GRAVITY: "1.052",
    PRE_BOIL_VOLUME: "20",
    KNOCKOUT_TEMPERATURE: "18",
    KNOCKOUT_VOLUME: "19",
    PITCH_TEMPERATURE: "18",
  };
  const pending = (
    (body.requirements ?? []) as Array<{
      class: string;
      status: string;
      required: boolean;
      stage_instance_id?: string;
      definition_key?: string;
    }>
  ).filter(
    (item) =>
      item.required &&
      item.class === "MEASUREMENT" &&
      ["PENDING", "DUE"].includes(item.status) &&
      item.stage_instance_id === activeId &&
      Boolean(item.definition_key),
  );
  for (const item of pending) {
    const type = item.definition_key as string;
    await recordMeasurement(page, type, values[type] ?? "1.050");
  }
}

export async function currentStageKey(page: Page) {
  const heading = ((await page.locator("h1").first().innerText().catch(() => "")) || "")
    .trim()
    .replaceAll(" ", "_")
    .toUpperCase();
  return heading;
}

export async function startAuxTimer(page: Page, name: string, seconds: number) {
  await page.getByLabel("Auxiliary timer name").fill(name);
  await page.getByLabel("Duration (seconds)").fill(String(seconds));
  await clickAndWait(
    page,
    page.getByRole("button", { name: "Start auxiliary timer" }),
    "/timers",
  );
}

export async function addBrewNote(page: Page, body: string) {
  await page.getByLabel("Brew-day note").fill(body);
  await clickAndWait(page, page.getByRole("button", { name: "Add note" }), "/notes");
  await expect(page.getByText(body)).toBeVisible();
}

export async function uploadCanonicalPhoto(page: Page) {
  const photo = page.getByLabel("Photo");
  await expect(photo).toBeVisible({ timeout: 10_000 });
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    "base64",
  );
  await photo.setInputFiles({ name: "e2e-canonical.png", mimeType: "image/png", buffer: png });
  await page.getByLabel("Caption").fill("E2E canonical attachment");
  await clickAndWait(page, page.getByRole("button", { name: "Upload photo" }), "/attachments");
  await expect(page.getByText("E2E canonical attachment")).toBeVisible();
}

export async function completePendingChecklists(page: Page) {
  for (let i = 0; i < 12; i += 1) {
    const button = page.getByRole("button", { name: "Mark complete" }).first();
    if (!(await button.isVisible().catch(() => false))) return;
    await clickAndWait(page, button, "/complete");
  }
}

export async function waivePendingIfAvailable(page: Page, reason: string) {
  const item = page
    .getByRole("listitem")
    .filter({ has: page.getByRole("button", { name: "Waive" }) })
    .filter({ hasText: /LIQUOR_READY|MILLING_DONE|REMINDER|ADDITION:/ })
    .first();
  if (!(await item.isVisible().catch(() => false))) return false;
  await item.getByLabel("Waiver reason (required)").fill(reason);
  await clickAndWait(page, item.getByRole("button", { name: "Waive" }), "/waivers");
  return true;
}

export async function waiveAllPending(page: Page, reason: string) {
  let any = false;
  for (let i = 0; i < 4; i += 1) {
    if (!(await waivePendingIfAvailable(page, reason))) break;
    any = true;
  }
  return any;
}

export async function executeVisibleAdditions(
  page: Page,
  options: { late: boolean; correct: boolean },
) {
  const result = { executed: false, late: false, corrected: false };
  if (options.late) {
    const lates = page.getByRole("button", { name: "Record late" });
    const lateCount = await lates.count();
    for (let i = 0; i < lateCount; i += 1) {
      const button = lates.nth(i);
      if (!(await button.isVisible().catch(() => false))) continue;
      const response = await clickAndWait(page, button, "/additions", { allowConflict: true });
      if (response.ok()) {
        result.late = true;
        break;
      }
    }
  }
  const executedButtons = page.getByRole("button", { name: "Record executed" });
  const executedCount = await executedButtons.count();
  for (let i = 0; i < executedCount; i += 1) {
    const button = executedButtons.nth(i);
    if (!(await button.isVisible().catch(() => false))) continue;
    const response = await clickAndWait(page, button, "/additions", { allowConflict: true });
    if (response.ok()) {
      result.executed = true;
      break;
    }
  }
  const correct = page.getByRole("button", { name: "Correct addition" }).first();
  if (options.correct && (await correct.isVisible().catch(() => false))) {
    await clickAndWait(page, correct, "/corrections");
    result.corrected = true;
  }
  return result;
}

export async function acknowledgeDueReminder(page: Page) {
  const due = page.getByRole("region", { name: "Required actions" }).getByRole("button", {
    name: "Acknowledge",
  }).first();
  if (await due.isVisible().catch(() => false)) {
    await clickAndWait(page, due, "/reminders/");
    return true;
  }
  return false;
}

export function seconds(value: string): number {
  const [hours, minutes, secs] = value.split(":").map(Number);
  return hours * 3600 + minutes * 60 + secs;
}

export async function assertRefreshRecovery(page: Page) {
  const timer = page.getByTestId("mash-timer");
  await expect(timer).toBeVisible();
  const before = seconds(await timer.innerText());
  const timerCount = await page.getByRole("list", { name: "Active timers" }).getByRole("listitem").count();
  const stage = await currentStageKey(page);
  await page.waitForTimeout(1_200);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Stage progress" })).toBeVisible({ timeout: 20_000 });
  await expect(timer).toBeVisible();
  const after = seconds(await timer.innerText());
  expect(after).toBeGreaterThanOrEqual(before + 1);
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText(/ACTIVE|PAUSED/);
  expect(await currentStageKey(page)).toBe(stage);
  if (timerCount > 0) {
    await expect(page.getByRole("list", { name: "Active timers" }).getByRole("listitem")).toHaveCount(
      timerCount,
    );
  }
}

export async function assertBrewDayA11y(page: Page, options?: { mobile?: boolean }) {
  await expect(page.getByRole("heading", { name: "Stage progress" })).toBeVisible();
  const pause = page.getByRole("button", { name: "Pause session" });
  if (await pause.isVisible().catch(() => false)) {
    await pause.focus();
    await expect(pause).toBeFocused();
    await page.keyboard.press("Tab");
  }
  const pH = page.getByLabel("pH reading");
  if (await pH.isVisible().catch(() => false)) {
    await expect(pH).toBeVisible();
    await expect(page.getByLabel("pH method")).toBeVisible();
    await expect(page.getByRole("button", { name: "Record pH" })).toBeVisible();
  }
  const timer = page.getByTestId("mash-timer");
  if (await timer.isVisible().catch(() => false)) {
    await expect(timer).toHaveAttribute("role", "timer");
    await expect(page.getByRole("region", { name: "Mash timer status" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Mash timer status" }).locator("[aria-live]")).toBeVisible();
    const box = await timer.boundingBox();
    expect(box).toBeTruthy();
    if (options?.mobile && box) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.y).toBeGreaterThanOrEqual(0);
      const viewport = page.viewportSize();
      if (viewport) {
        expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1);
        expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 1);
      }
    }
  }
  const reminders = page.getByRole("region", { name: "Required actions" });
  if (await reminders.isVisible().catch(() => false)) {
    await expect(reminders).toHaveAttribute("aria-live", "polite");
  }
  await expect(page.getByRole("status", { name: "Session status" })).toBeVisible();
  const abort = page.getByRole("button", { name: "Abort session" });
  if (await abort.isVisible().catch(() => false)) {
    await expect(page.getByLabel("Abort reason")).toBeVisible();
    await expect(abort).toBeDisabled();
  }
  const photo = page.getByLabel("Photo");
  if (await photo.isVisible().catch(() => false)) {
    await expect(page.getByLabel("Caption")).toBeVisible();
    await expect(page.getByRole("button", { name: "Upload photo" })).toBeVisible();
  }
  const waiver = page.getByLabel("Waiver reason (required)");
  if (await waiver.isVisible().catch(() => false)) {
    await expect(waiver).toBeVisible();
    await expect(page.getByRole("button", { name: "Waive" }).first()).toBeDisabled();
  }
  const voiceDialog = page.getByRole("dialog", { name: "Voice measurement confirmation" });
  if (await voiceDialog.isVisible().catch(() => false)) {
    await expect(page.getByRole("button", { name: "Confirm voice measurement" })).toBeVisible();
  }
  await expect(page.getByLabel("Auxiliary timer name")).toBeVisible();
  await expect(page.getByLabel("Duration (seconds)")).toBeVisible();
}

export async function assertErrorAssociation(page: Page) {
  const alert = page.locator("#brew-session-error, #ferment-session-error");
  await expect(alert).toBeVisible();
  await expect(alert).toHaveAttribute("role", "alert");
  await expect(alert).toBeFocused();
}

export async function waitForFermentIdle(page: Page) {
  const sheet = page.getByTestId("ferment-worksheet");
  await expect(sheet).toBeVisible({ timeout: 20_000 });
  await expect(sheet).toHaveAttribute("data-busy", "false", { timeout: 20_000 });
}

export async function clickAndWaitFerment(
  page: Page,
  button: Locator,
  urlPart: string,
  options?: { allowConflict?: boolean },
) {
  await expect(button).toBeEnabled({ timeout: 20_000 });
  const pending = page.waitForResponse(isPostTo(urlPart), { timeout: 20_000 });
  await button.click();
  const response = await pending;
  if (options?.allowConflict && response.status() === 409) {
    await waitForFermentIdle(page);
    return response;
  }
  if (!response.ok()) {
    throw new Error(`${urlPart} failed: ${response.status()} ${await response.text()}`);
  }
  await waitForFermentIdle(page);
  return response;
}

export async function assertFermentA11y(page: Page, options?: { mobile?: boolean }) {
  await expect(page.getByRole("heading", { name: "Lifecycle stages" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Session status" })).toBeVisible();
  const gravity = page.getByLabel("Gravity reading");
  if (await gravity.isVisible().catch(() => false)) {
    await gravity.focus();
    await expect(gravity).toBeFocused();
    await expect(page.getByLabel("Measurement note")).toBeVisible();
    await expect(page.getByRole("button", { name: "Record gravity" })).toBeVisible();
    const box = await gravity.boundingBox();
    expect(box).toBeTruthy();
    if (options?.mobile && box) {
      const viewport = page.viewportSize();
      if (viewport) {
        expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1);
      }
    }
  }
  const reminders = page.getByRole("region", { name: "Required actions" });
  if (await reminders.isVisible().catch(() => false)) {
    await expect(reminders).toHaveAttribute("aria-live", "polite");
    await expect(reminders.getByRole("button", { name: "Acknowledge" }).first()).toBeVisible();
  }
}

/** API-seed a completed legacy brew + ACTIVE fermentation for Phase 4 worksheet E2E. */
export async function seedActiveFermentation(page: Page, label: string) {
  await clearActiveBrew(page);
  const origin = e2eOrigin();
  const headers = await csrfHeaders(page, origin);
  const recipe = await createLegacyRecipe(page, label);
  const brew = await postJson(
    page.request,
    "/api/v1/brew-sessions",
    { recipe_version_id: recipe.version_id, operation_id: `e2e-ferm-create-${Date.now()}` },
    headers,
  );
  let details = await page.request.get(`/api/v1/brew-sessions/${brew.id}`, {
    headers: { Origin: origin },
  });
  if (!details.ok()) throw new Error(`brew details failed: ${details.status()}`);
  let revision = (await details.json()).revision as number;
  await postJson(
    page.request,
    `/api/v1/brew-sessions/${brew.id}/start`,
    { operation_id: `e2e-ferm-start-${Date.now()}`, expected_revision: revision },
    headers,
  );
  details = await page.request.get(`/api/v1/brew-sessions/${brew.id}`, {
    headers: { Origin: origin },
  });
  revision = (await details.json()).revision as number;
  const mash = await postJson(
    page.request,
    `/api/v1/brew-sessions/${brew.id}/mash/start`,
    { operation_id: `e2e-ferm-mash-${Date.now()}`, expected_revision: revision },
    headers,
  );
  await postJson(
    page.request,
    `/api/v1/brew-sessions/stages/${mash.id}/measurements`,
    {
      measurement_type: "MASH_PH",
      value: "5.30",
      unit: "pH",
      operation_id: `e2e-ferm-ph-${Date.now()}`,
      method: "METER",
      sample_temperature_c: "65.00",
      temperature_compensated: true,
    },
    headers,
  );
  await postJson(
    page.request,
    `/api/v1/brew-sessions/stages/${mash.id}/measurements`,
    {
      measurement_type: "MASH_GRAVITY",
      value: "1.048",
      unit: "SG",
      operation_id: `e2e-ferm-sg-${Date.now()}`,
      method: "HYDROMETER",
      sample_temperature_c: "20.00",
    },
    headers,
  );
  details = await page.request.get(`/api/v1/brew-sessions/${brew.id}`, {
    headers: { Origin: origin },
  });
  revision = (await details.json()).revision as number;
  await postJson(
    page.request,
    `/api/v1/brew-sessions/${brew.id}/pitch-handoff`,
    {
      yeast_addition_note: "E2E US-05 pitched for Phase 4 worksheet",
      pitch_temperature_c: "18.0",
      operation_id: `e2e-ferm-pitch-${Date.now()}`,
      expected_revision: revision,
    },
    headers,
  );
  details = await page.request.get(`/api/v1/brew-sessions/${brew.id}`, {
    headers: { Origin: origin },
  });
  revision = (await details.json()).revision as number;
  await postJson(
    page.request,
    `/api/v1/brew-sessions/stages/${mash.id}/complete`,
    { operation_id: `e2e-ferm-mash-complete-${Date.now()}`, expected_revision: revision },
    headers,
  );
  const fermentation = await postJson(
    page.request,
    `/api/v1/fermentation-sessions/brew-sessions/${brew.id}/start`,
    { operation_id: `e2e-ferm-session-${Date.now()}` },
    headers,
  );
  const activeStage = (fermentation.stages as Array<{ id: string; canonical_stage_type: string }>).find(
    (stage) => stage.canonical_stage_type === "ACTIVE_FERMENTATION",
  );
  if (!activeStage) throw new Error("ACTIVE_FERMENTATION stage missing after start");
  await postJson(
    page.request,
    `/api/v1/fermentation-sessions/${fermentation.id}/measurements`,
    {
      operation_id: `e2e-ferm-gravity-${Date.now()}`,
      measurement_type: "FERMENTATION_GRAVITY",
      value: "1.020",
      unit: "SG",
      observed_at: new Date().toISOString(),
      stage_instance_id: activeStage.id,
      source: "OBSERVED",
      method: "HYDROMETER",
      sample_temperature_c: "20.00",
      note: "Seeded gravity leaf for worksheet E2E",
      expected_revision: fermentation.revision,
    },
    headers,
  );
  const refreshed = await page.request.get(`/api/v1/fermentation-sessions/${fermentation.id}`, {
    headers: { Origin: origin },
  });
  if (!refreshed.ok()) throw new Error(`ferment refresh failed: ${refreshed.status()}`);
  const current = await refreshed.json();
  return {
    brewSessionId: brew.id as string,
    fermentationSessionId: fermentation.id as string,
    revision: current.revision as number,
    stages: current.stages as Array<{ id: string; canonical_stage_type: string; status: string }>,
  };
}

