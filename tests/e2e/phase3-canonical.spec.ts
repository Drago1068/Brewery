import { expect, test, type Page } from "@playwright/test";

import {
  addBrewNote,
  assertBrewDayA11y,
  assertRefreshRecovery,
  clearActiveBrew,
  clickAndWait,
  completePendingChecklists,
  csrfHeaders,
  currentStageKey,
  e2eOrigin,
  executeVisibleAdditions,
  postJson,
  recordMeasurement,
  recordVisibleStageMeasurements,
  signIn,
  startAuxTimer,
  uploadCanonicalPhoto,
  waitForBrewIdle,
  waiveAllPending,
} from "./helpers";

const REQUIRED_STAGES = [
  "PRE_BREW",
  "WATER_PREPARATION",
  "MASH_IN",
  "MASH",
  "PRE_BOIL",
  "BOIL",
  "WHIRLPOOL_FLAMEOUT",
  "CHILL",
  "TRANSFER",
  "YEAST_PITCH",
  "BREW_COMPLETE",
] as const;

async function createPhase3Recipe(page: Page, stamp: number) {
  const origin = e2eOrigin();
  const headers = await csrfHeaders(page, origin);
  const equipment = await postJson(
    page.request,
    "/api/v1/equipment-profiles",
    {
      name: `E2E System ${stamp}`,
      default_batch_liters: "20",
      brewhouse_efficiency: "0.75",
      boil_off_liters_per_hour: "3",
    },
    headers,
  );
  const location = await postJson(
    page.request,
    "/api/v1/inventory/locations",
    { name: `E2E Grain ${stamp}` },
    headers,
  );
  const malt = await postJson(
    page.request,
    "/api/v1/ingredients",
    {
      name: `E2E Malt ${stamp}`,
      category: "FERMENTABLE",
      canonical_unit: "g",
      attributes: { potential_ppg: "36", color_lovibond: "3" },
    },
    headers,
  );
  const hop = await postJson(
    page.request,
    "/api/v1/ingredients",
    {
      name: `E2E Hop ${stamp}`,
      category: "HOP",
      canonical_unit: "g",
      attributes: { alpha_acid_percent: "6.2" },
    },
    headers,
  );
  const yeast = await postJson(
    page.request,
    "/api/v1/ingredients",
    {
      name: `E2E Yeast ${stamp}`,
      category: "YEAST",
      canonical_unit: "each",
      attributes: {},
    },
    headers,
  );
  for (const [ingredient, qty, code, alpha] of [
    [malt.id, "10000", `MALT-${stamp}`, null],
    [hop.id, "200", `HOP-${stamp}`, "6.2"],
    [yeast.id, "2", `YEAST-${stamp}`, null],
  ] as const) {
    await postJson(
      page.request,
      "/api/v1/ingredient-lots",
      {
        ingredient_id: ingredient,
        lot_code: code,
        received_quantity: qty,
        unit: ingredient === yeast.id ? "each" : "g",
        location_id: location.id,
        hop_alpha_acid_percent: alpha,
      },
      headers,
    );
  }
  const design = await postJson(
    page.request,
    "/api/v1/recipe-designs",
    {
      name: `Canonical Phase3 ${stamp}`,
      equipment_profile_id: equipment.id,
      batch_size_liters: "20",
      planned_mash_duration_minutes: 1,
      boil_duration_minutes: 60,
      ingredients: [
        { ingredient_id: malt.id, amount: "5000", unit: "g", use_stage: "MASH" },
        {
          ingredient_id: hop.id,
          amount: "20",
          unit: "g",
          use_stage: "BOIL",
          timing_minutes: 15,
        },
        {
          ingredient_id: hop.id,
          amount: "10",
          unit: "g",
          use_stage: "WHIRLPOOL",
          timing_minutes: 0,
        },
        { ingredient_id: yeast.id, amount: "1", unit: "each", use_stage: "FERMENTATION" },
      ],
      process_steps: [
        {
          step_type: "MASH",
          sequence: 1,
          name: "Saccharification",
          duration_minutes: 1,
          temperature_c: "66.67",
        },
        { step_type: "BOIL", sequence: 2, name: "Boil", duration_minutes: 60 },
      ],
    },
    headers,
  );
  return design as { version_id: string; name: string };
}

async function startBrewFromHome(page: Page, recipeName: string) {
  await page.goto("/");
  await clearActiveBrew(page);
  const origin = e2eOrigin();
  const headers = await csrfHeaders(page, origin);
  const recipes = await page.request.get("/api/v1/recipes", { headers: { Origin: origin } });
  if (!recipes.ok()) throw new Error(`Recipe list failed: ${recipes.status()}`);
  const list = (await recipes.json()) as Array<{ name: string; version_id: string }>;
  const match = list.find((item) => item.name === recipeName);
  if (!match) throw new Error(`Recipe ${recipeName} not found in API list`);
  const session = await postJson(
    page.request,
    "/api/v1/brew-sessions",
    { recipe_version_id: match.version_id, operation_id: `e2e-create-${Date.now()}` },
    headers,
  );
  const details = await page.request.get(`/api/v1/brew-sessions/${session.id}`, {
    headers: { Origin: origin },
  });
  if (!details.ok()) {
    throw new Error(`Session details failed: ${details.status()} ${await details.text()}`);
  }
  const revision = (await details.json()).revision as number;
  await postJson(
    page.request,
    `/api/v1/brew-sessions/${session.id}/start`,
    { operation_id: `e2e-start-${Date.now()}`, expected_revision: revision },
    headers,
  );
  await page.goto(`/brew/${session.id}`);
  await expect(page.getByRole("heading", { name: "Stage progress" })).toBeVisible({ timeout: 20_000 });
}

async function startCurrentStage(page: Page) {
  const startMash = page.getByRole("button", { name: "Start Mash", exact: true });
  if (await startMash.isVisible().catch(() => false)) {
    await clickAndWait(page, startMash, "/mash/start");
    await expect(page.getByTestId("mash-timer")).toBeVisible({ timeout: 20_000 });
    return "MASH";
  }
  const start = page.getByTestId("start-current-stage");
  if (await start.isVisible().catch(() => false)) {
    const label = await start.innerText();
    await clickAndWait(page, start, "/start");
    return label.replace(/^Start\s+/, "");
  }
  return null;
}

async function skipOptionalIfBetweenStages(page: Page) {
  const start = page.getByTestId("start-current-stage");
  if (!(await start.isVisible().catch(() => false))) return false;
  const label = await start.innerText();
  if (!/MILLING|LAUTER_SPARGE/.test(label)) return false;
  const skip = page.getByRole("button", { name: /^Skip / }).first();
  if (!(await skip.isVisible().catch(() => false))) return false;
  await clickAndWait(page, skip, "/skip");
  return true;
}

async function completeCurrentStage(page: Page) {
  const mashComplete = page.getByRole("button", { name: "Complete Mash", exact: true });
  if (await mashComplete.isVisible().catch(() => false)) {
    await clickAndWait(page, mashComplete, "/complete");
    return "MASH";
  }
  const complete = page
    .getByRole("button", { name: /^Complete / })
    .filter({ hasNotText: "brew session" })
    .first();
  if (await complete.isVisible().catch(() => false)) {
    const label = await complete.innerText();
    await clickAndWait(page, complete, "/complete");
    return label;
  }
  return null;
}

async function confirmVoiceMeasurement(page: Page) {
  const confirm = page.getByRole("button", { name: "Confirm voice measurement" });
  if (await confirm.isVisible().catch(() => false)) {
    await clickAndWait(page, confirm, "/measurements");
    return true;
  }
  await page.getByPlaceholder("five point two pH").fill("five point three zero pH");
  await page.getByRole("button", { name: "Parse transcript" }).click();
  await expect(page.getByRole("dialog", { name: "Voice measurement confirmation" })).toBeVisible();
  await expect(page.getByText("Proposed MASH_PH:")).toBeVisible();
  await clickAndWait(
    page,
    page.getByRole("button", { name: "Confirm voice measurement" }),
    "/measurements",
  );
  return true;
}

async function exerciseRepeatMash(page: Page) {
  const reason = page.getByLabel("Repeat/return reason");
  await expect(reason).toBeVisible({ timeout: 10_000 });
  await reason.fill("E2E canonical repeat after mash completion");
  const repeat = page.getByRole("button", { name: "Repeat Mash" });
  await expect(repeat).toBeVisible();
  await clickAndWait(page, repeat, "/repeat");
  await expect(
    page
      .getByRole("region", { name: "Stage progress" })
      .getByRole("listitem")
      .filter({ hasText: "MASH" })
      .filter({ hasText: "#2" }),
  ).toBeVisible({
    timeout: 15_000,
  });
}

async function recordYeastPitch(page: Page) {
  await page.getByLabel("Yeast pitch note").fill("Pitched one pack US-05 after chill");
  await clickAndWait(page, page.getByRole("button", { name: "Record yeast pitch" }), "/pitch-handoff");
}

test("canonical Phase 3 brew-day flow PRE_BREW through BREW_COMPLETE", async ({ page }) => {
  test.setTimeout(600_000);
  const stamp = Date.now();
  await signIn(page);
  const recipe = await createPhase3Recipe(page, stamp);
  await startBrewFromHome(page, recipe.name);

  await expect(page.getByRole("listitem").filter({ hasText: "PRE_BREW" }).first()).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "YEAST_PITCH" }).first()).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "BREW_COMPLETE" }).first()).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "WHIRLPOOL_FLAMEOUT" }).first()).toBeVisible();

  const visited = new Set<string>();
  let mashExtrasDone = false;
  let mashRepeated = false;
  let waived = false;
  let recordedLate = false;
  let recordedCorrection = false;
  let confirmedVoice = false;
  let uploadedMedia = false;

  for (let step = 0; step < 60; step += 1) {
    const statusLocator = page
      .getByRole("status", { name: "Session status" })
      .or(page.locator(".brew-topbar .status"))
      .first();
    await expect(statusLocator).toBeVisible({ timeout: 20_000 });
    const status = (await statusLocator.innerText()).trim();
    if (status === "COMPLETED") break;

    if (await skipOptionalIfBetweenStages(page)) continue;

    const started = await startCurrentStage(page);
    const stageKey = (started ?? (await currentStageKey(page))).replaceAll(" ", "_").toUpperCase();
    if (stageKey && stageKey !== "SKIPPED") visited.add(stageKey);

    await completePendingChecklists(page);
    if (stageKey === "MASH" && !mashExtrasDone) {
      confirmedVoice = await confirmVoiceMeasurement(page);
    }
    await recordVisibleStageMeasurements(page, stageKey);
    if (await waiveAllPending(page, "Observed condition satisfies operational intent")) {
      waived = true;
    }

    const addition = await executeVisibleAdditions(page, {
      late: !recordedLate,
      correct: !recordedCorrection,
    });
    if (addition.late) recordedLate = true;
    if (addition.corrected) recordedCorrection = true;

    if (stageKey === "MASH" && !mashExtrasDone) {
      mashExtrasDone = true;
      await assertBrewDayA11y(page);
      await startAuxTimer(page, "Iodine check", 90);
      await startAuxTimer(page, "Hop stand prep", 90);
      await expect(page.getByRole("list", { name: "Active timers" }).getByRole("listitem")).toHaveCount(
        3,
        { timeout: 15_000 },
      );
      const due = page
        .getByRole("region", { name: "Required actions" })
        .getByRole("button", { name: "Acknowledge" })
        .first();
      if (await due.isVisible().catch(() => false)) {
        await due.click();
        await waitForBrewIdle(page);
      }
      const extrasAdd = await executeVisibleAdditions(page, {
        late: !recordedLate,
        correct: !recordedCorrection,
      });
      if (extrasAdd.late) recordedLate = true;
      if (extrasAdd.corrected) recordedCorrection = true;
      await addBrewNote(page, "Full-stage canonical note");
      await uploadCanonicalPhoto(page);
      uploadedMedia = true;
      await assertRefreshRecovery(page);
      await expect(page.getByText("Full-stage canonical note")).toBeVisible();
      await expect(page.getByText("E2E canonical attachment")).toBeVisible();
      await expect(page.getByTestId("mash-timer")).toBeVisible();
    }

    if (stageKey === "YEAST_PITCH") {
      await recordYeastPitch(page);
    }

    await executeVisibleAdditions(page, {
      late: !recordedLate,
      correct: !recordedCorrection,
    }).then((again) => {
      if (again.late) recordedLate = true;
      if (again.corrected) recordedCorrection = true;
    });
    if (await waiveAllPending(page, "Observed condition satisfies operational intent")) {
      waived = true;
    }
    await completePendingChecklists(page);

    const completed = await completeCurrentStage(page);
    if (completed === "MASH" && !mashRepeated) {
      await exerciseRepeatMash(page);
      mashRepeated = true;
      continue;
    }

    if (stageKey === "BREW_COMPLETE") {
      const completeSession = page.getByRole("button", { name: "Complete brew session" });
      await clickAndWait(page, completeSession, "/complete");
      await expect(page.getByRole("status", { name: "Session status" })).toHaveText("COMPLETED", {
        timeout: 20_000,
      });
      break;
    }
  }

  if (!mashExtrasDone) throw new Error("Mash extras (timers/note/media/voice) never ran");
  if (!mashRepeated) throw new Error("Repeat Mash was never exercised after mash completion");
  if (!confirmedVoice) throw new Error("Voice confirmation never committed a measurement");
  if (!uploadedMedia) throw new Error("Canonical media upload never completed");
  if (!recordedLate) throw new Error("Late addition was never recorded");
  if (!recordedCorrection) throw new Error("Addition correction was never recorded");
  if (!waived) throw new Error("Waiver control was never used");
  for (const stage of REQUIRED_STAGES) {
    expect(visited.has(stage) || (await page.getByText(stage).first().isVisible())).toBeTruthy();
  }

  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mash performance" })).toBeVisible();
  await expect(page.locator(".performance")).toContainText("Mash pH");
  await expect(page.locator(".performance")).toContainText("Mash gravity");
  await expect(page.getByText("Full-stage canonical note")).toBeVisible();
  await expect(page.getByText("E2E canonical attachment")).toBeVisible();
  await expect(page.getByText(/Pitched one pack US-05|Yeast pitch recorded/)).toBeVisible();
  await expect(page.getByText("Mash completed").first()).toBeVisible();
  await expect(page.getByText(/Addition executed|Late addition/i).first()).toBeVisible();
  for (const stage of REQUIRED_STAGES) {
    await expect(page.getByText(stage).first()).toBeVisible();
  }
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText("COMPLETED");
});
