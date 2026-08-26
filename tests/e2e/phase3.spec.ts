import { expect, test, type Page } from "@playwright/test";

import {
  addBrewNote,
  assertBrewDayA11y,
  assertErrorAssociation,
  assertRefreshRecovery,
  clearActiveBrew,
  createLegacyRecipe,
  reachAndStartMash,
  recordMashGravity,
  recordMashPh,
  signIn,
  startAuxTimer,
  startBrewFromRecipeCard,
} from "./helpers";

async function signInAndStartMash(page: Page, recipeName: string) {
  await signIn(page);
  await clearActiveBrew(page);
  await createLegacyRecipe(page, recipeName);
  await startBrewFromRecipeCard(page, recipeName);
  await reachAndStartMash(page);
}

test("voice draft cannot commit fifty-two as mash pH", async ({ page }) => {
  await signInAndStartMash(page, `Voice Gate ${Date.now()}`);
  await page.getByPlaceholder("five point two pH").fill("fifty two pH");
  await page.getByRole("button", { name: "Parse transcript" }).click();
  await expect(page.getByRole("dialog", { name: "Voice measurement confirmation" })).toBeVisible();
  await expect(page.getByText("Proposed MASH_PH:")).toBeVisible();
  await expect(page.getByText("52 pH")).toBeVisible();
  const confirm = page.getByRole("button", { name: "Confirm voice measurement" });
  await confirm.focus();
  await expect(confirm).toBeFocused();
  await confirm.click();
  await assertErrorAssociation(page);
  await expect(page.locator("#brew-session-error")).toContainText(/pH|0 and 14|between/i);
  await expect(page.getByLabel("pH reading")).toBeVisible();
});

test("pause, resume, refresh recovery, and journal remain authoritative", async ({ page }) => {
  await signInAndStartMash(page, `Recovery ${Date.now()}`);
  await page.getByRole("button", { name: "Pause session" }).click();
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText("PAUSED");
  await page.reload();
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText("PAUSED");
  await expect(page.getByRole("heading", { name: "Stage progress" })).toBeVisible();
  await page.getByRole("button", { name: "Resume session" }).click();
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText("ACTIVE");
  await recordMashPh(page, "5.42");
  await expect(page.locator(".measurement-card.done strong").filter({ hasText: "5.420" })).toBeVisible();
  await recordMashGravity(page, "1.048");
  await expect(page.locator(".measurement-card.done strong").filter({ hasText: "1.048" })).toBeVisible();
  await page.getByRole("button", { name: "Complete Mash", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Mash performance" })).toBeVisible();
  await expect(page.locator(".performance").getByText("5.420", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText("COMPLETED", {
    timeout: 20_000,
  });
});

test("phone viewport keeps mash timer and measurement controls usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAndStartMash(page, `Phone Brew ${Date.now()}`);
  await assertBrewDayA11y(page, { mobile: true });
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  await expect(page.getByLabel("pH reading")).toBeVisible();
  await expect(page.getByRole("button", { name: "Record pH" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pause session" })).toBeVisible();
  await page.getByRole("button", { name: "Record pH" }).focus();
  await expect(page.getByRole("button", { name: "Record pH" })).toBeFocused();
});

test("tablet viewport and keyboard focus remain usable", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await signInAndStartMash(page, `Tablet Brew ${Date.now()}`);
  await assertBrewDayA11y(page);
  await expect(page.getByTestId("mash-timer")).toBeVisible();
  const record = page.getByRole("button", { name: "Record pH" });
  await record.focus();
  await expect(record).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Gravity reading")).toBeVisible();
  await expect(page.getByLabel("Transcript")).toBeVisible();
  const transcript = page.getByLabel("Transcript");
  await transcript.focus();
  await expect(transcript).toBeFocused();
});

test("canonical brew-day controls: three timers, reminders, note, refresh, journal", async ({ page }) => {
  await signInAndStartMash(page, `Canonical Mash ${Date.now()}`);
  await startAuxTimer(page, "Hop check", 120);
  await startAuxTimer(page, "Iodine check", 120);
  await expect(page.getByRole("list", { name: "Active timers" }).getByRole("listitem")).toHaveCount(3, {
    timeout: 15_000,
  });
  const due = page
    .getByRole("region", { name: "Required actions" })
    .getByRole("button", { name: "Acknowledge" })
    .first();
  if (await due.isVisible().catch(() => false)) {
    await due.click();
  }
  await recordMashPh(page, "5.30");
  await recordMashGravity(page, "1.050");
  await addBrewNote(page, "Canonical note for journal evidence");
  await assertRefreshRecovery(page);
  await expect(page.getByText("Canonical note for journal evidence")).toBeVisible();
  await expect(page.getByRole("list", { name: "Active timers" }).getByRole("listitem")).toHaveCount(3);
  await page.getByRole("button", { name: "Complete Mash", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Stage progress" })).toBeVisible();
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText("COMPLETED", {
    timeout: 20_000,
  });
});
