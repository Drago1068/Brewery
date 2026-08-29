import { expect, test } from "@playwright/test";

import {
  clearActiveBrew,
  createLegacyRecipe,
  reachAndStartMash,
  signIn,
  startBrewFromRecipeCard,
} from "./helpers";

/**
 * Browser-side performance sampler for P3-FR-088 / P3-IMPL-RR-008.
 * Collects navigation + dashboard recovery samples across two authenticated tabs.
 * Opt in with PHASE3_PERF_BROWSER=1 (default sample count 30).
 */
test("browser performance sampler records navigation and recovery samples", async ({ browser }) => {
  test.skip(process.env.PHASE3_PERF_BROWSER !== "1", "Set PHASE3_PERF_BROWSER=1 for normative browser sampling");
  test.setTimeout(300_000);
  const samples = Number(process.env.PHASE3_PERF_BROWSER_SAMPLES ?? "30");
  const recipeName = `Perf Browser ${Date.now()}`;

  const contextA = await browser.newContext();
  const pageA = await contextA.newPage();
  await signIn(pageA);
  await clearActiveBrew(pageA);
  await createLegacyRecipe(pageA, recipeName);
  await startBrewFromRecipeCard(pageA, recipeName);
  await reachAndStartMash(pageA);
  await expect(pageA.getByTestId("mash-timer")).toBeVisible();

  const contextB = await browser.newContext();
  const pageB = await contextB.newPage();
  await signIn(pageB);
  await pageB.goto(pageA.url());
  await expect(pageB.getByTestId("mash-timer")).toBeVisible({ timeout: 20_000 });

  const statusOf = (page: typeof pageA) => page.getByRole("status", { name: "Session status" });

  const navigationMs: number[] = [];
  const recoveryMs: number[] = [];
  for (let i = 0; i < samples; i += 1) {
    const target = i % 2 === 0 ? pageA : pageB;
    const navStarted = Date.now();
    await target.reload();
    await expect(target.getByTestId("mash-timer")).toBeVisible({ timeout: 20_000 });
    navigationMs.push(Date.now() - navStarted);

    const recoveryStarted = Date.now();
    await target.getByRole("button", { name: "Pause session" }).click();
    await expect(statusOf(target)).toHaveText("PAUSED", { timeout: 15_000 });
    await target.reload();
    await expect(statusOf(target)).toHaveText("PAUSED", { timeout: 15_000 });
    await target.getByRole("button", { name: "Resume session" }).click();
    await expect(statusOf(target)).toHaveText("ACTIVE", { timeout: 15_000 });
    recoveryMs.push(Date.now() - recoveryStarted);
  }

  const percentile = (values: number[], p: number) => {
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
    return sorted[index];
  };

  expect(navigationMs).toHaveLength(samples);
  expect(recoveryMs).toHaveLength(samples);
  expect(percentile(navigationMs, 95)).toBeLessThan(15_000);
  expect(percentile(recoveryMs, 95)).toBeLessThan(20_000);

  await contextA.close();
  await contextB.close();
});
