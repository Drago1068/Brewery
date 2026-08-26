import { expect, test } from "@playwright/test";

import {
  assertBrewDayA11y,
  assertRefreshRecovery,
  clearActiveBrew,
  createLegacyRecipe,
  reachAndStartMash,
  recordMashGravity,
  recordMashPh,
  seconds,
  signIn,
  startBrewFromRecipeCard,
} from "./helpers";

test("complete Phase 1A workflow and recover the Mash timer after refresh", async ({ page }) => {
  const recipeName = `Architecture Ale ${Date.now()}`;
  await signIn(page);
  await clearActiveBrew(page);
  await createLegacyRecipe(page, recipeName);
  await startBrewFromRecipeCard(page, recipeName);
  await reachAndStartMash(page);
  await assertBrewDayA11y(page);

  const requiredActions = page.getByRole("region", { name: "Required actions" });
  await expect(requiredActions.getByText("Measure Mash pH", { exact: true })).toBeVisible();
  await expect(requiredActions.getByText("Measure Mash Gravity", { exact: true })).toBeVisible();
  await expect(requiredActions).toHaveAttribute("aria-live", "polite");

  const timer = page.getByTestId("mash-timer");
  const before = seconds(await timer.innerText());
  await assertRefreshRecovery(page);
  const after = seconds(await timer.innerText());
  expect(after).toBeGreaterThanOrEqual(before + 1);

  await recordMashPh(page, "5.42");
  await expect(page.locator(".measurement-card.done strong").filter({ hasText: "5.420" })).toBeVisible();

  await recordMashGravity(page, "1.048");
  await expect(page.locator(".measurement-card.done strong").filter({ hasText: "1.048" })).toBeVisible();

  await Promise.all([
    page.waitForResponse(
      (response) => response.url().includes("/complete") && response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Complete Mash", exact: true }).click(),
  ]);

  await expect(page.getByRole("heading", { name: "Mash performance" })).toBeVisible();
  await expect(page.locator(".performance").getByText("5.420", { exact: true })).toBeVisible();
  await expect(page.locator(".performance").getByText("1.048 SG", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
  await expect(page.getByText("Mash completed")).toBeVisible();
  await expect(page.getByRole("status", { name: "Session status" })).toHaveText("COMPLETED", {
    timeout: 20_000,
  });
});
