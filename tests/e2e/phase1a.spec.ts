import { expect, test } from "@playwright/test";

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

  await page.getByLabel("Recipe name").fill(recipeName);
  await page.getByLabel("Duration (min)").fill("1");
  await page.getByRole("button", { name: "Create recipe v1" }).click();
  const recipeCard = page.getByRole("heading", { name: recipeName }).locator("..");
  await expect(recipeCard).toBeVisible();
  await recipeCard.getByRole("button", { name: "Start brew session" }).click();

  await expect(page.getByRole("heading", { name: "Ready to start Mash" })).toBeVisible();
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
  await page.getByRole("button", { name: "Record pH" }).click();
  await expect(page.getByText("Outside tolerance").first()).toBeVisible();

  await page.getByLabel("Gravity reading").fill("1.048");
  await page.getByRole("button", { name: "Record gravity" }).click();
  await page.getByRole("button", { name: "Complete Mash" }).click();

  await expect(page.getByText("COMPLETED", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mash performance" })).toBeVisible();
  await expect(page.getByText("5.420", { exact: true })).toBeVisible();
  await expect(page.getByText("1.048 SG", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Brew journal" })).toBeVisible();
  await expect(page.getByText("Mash completed")).toBeVisible();
});
