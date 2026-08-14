import { expect, test } from "@playwright/test";

test("voice draft cannot commit fifty-two as mash pH", async ({ page }) => {
  const recipeName = `Voice Gate ${Date.now()}`;
  await page.goto("/login");
  await page.getByLabel("Username").fill(process.env.E2E_USERNAME ?? "brewer");
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByLabel("Recipe name").fill(recipeName);
  await page.getByLabel("Duration (min)").fill("1");
  await page.getByRole("button", { name: "Create recipe v1" }).click();
  const recipeCard = page.getByRole("heading", { name: recipeName }).locator("..");
  await recipeCard.getByRole("button", { name: "Start brew session" }).click();
  await page.getByRole("button", { name: "Start Mash" }).click();
  await page.getByPlaceholder("five point two pH").fill("fifty two pH");
  await page.getByRole("button", { name: "Parse transcript" }).click();
  await expect(page.getByText("Proposed MASH_PH:")).toBeVisible();
  await expect(page.getByText("52 pH")).toBeVisible();
  await page.getByRole("button", { name: "Confirm voice measurement" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("pH reading")).toBeVisible();
});
