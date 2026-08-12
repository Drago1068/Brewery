import { expect, test } from "@playwright/test";

test("complete Phase 2 brewing-core vertical slice", async ({ page }) => {
  const stamp = Date.now();
  const equipmentName = `Pilot System ${stamp}`;
  const maltName = `Pale Malt ${stamp}`;
  const hopName = `Cascade ${stamp}`;
  const yeastName = `US-05 ${stamp}`;
  const locationName = `Grain Room ${stamp}`;
  const recipeName = `Phase Two Pale ${stamp}`;
  const postedTo = (suffix: string) => (response: { url(): string; request(): { method(): string } }) =>
    response.url().endsWith(suffix) && response.request().method() === "POST";

  await page.goto("/login");
  await page.getByLabel("Username").fill(process.env.E2E_USERNAME ?? "brewer");
  await page.getByLabel("Password").fill(process.env.E2E_PASSWORD ?? "");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Plan once. Brew with confidence." })).toBeVisible();
  await page.goto("/designer");
  await expect(page.getByRole("heading", { name: "Recipe Designer" })).toBeVisible();
  await page.waitForLoadState("networkidle");

  const equipment = page.getByRole("heading", { name: "Equipment profile" }).locator("..");
  await equipment.getByLabel("Name").fill(equipmentName);
  await Promise.all([
    page.waitForResponse(postedTo("/equipment-profiles")),
    equipment.getByRole("button", { name: "Save equipment" }).click({ force: true }),
  ]);
  await expect(equipment.getByRole("button", { name: "Save equipment" })).toBeEnabled();

  const inventory = page.locator(".inventory-setup");
  await inventory.getByLabel("Location name").fill(locationName);
  await Promise.all([
    page.waitForResponse(postedTo("/inventory/locations")),
    inventory.getByRole("button", { name: "Add location" }).click({ force: true }),
  ]);
  await expect(inventory.getByRole("button", { name: "Add location" })).toBeEnabled();

  const catalog = page.getByRole("heading", { name: "Add ingredient" }).locator("..");
  await catalog.getByLabel("Name").fill(maltName);
  await Promise.all([
    page.waitForResponse(postedTo("/ingredients")),
    catalog.getByRole("button", { name: "Add ingredient" }).click({ force: true }),
  ]);
  await expect(catalog.getByRole("button", { name: "Add ingredient" })).toBeEnabled();
  await catalog.getByLabel("Name").fill(hopName);
  await catalog.getByLabel("Category").selectOption("HOP");
  await catalog.getByLabel("Potential PPG / alpha %").fill("5.5");
  await Promise.all([
    page.waitForResponse(postedTo("/ingredients")),
    catalog.getByRole("button", { name: "Add ingredient" }).click({ force: true }),
  ]);
  await expect(catalog.getByRole("button", { name: "Add ingredient" })).toBeEnabled();
  await catalog.getByLabel("Name").fill(yeastName);
  await catalog.getByLabel("Category").selectOption("YEAST");
  await catalog.getByLabel("Canonical unit").selectOption("each");
  await Promise.all([
    page.waitForResponse(postedTo("/ingredients")),
    catalog.getByRole("button", { name: "Add ingredient" }).click({ force: true }),
  ]);
  await expect(catalog.getByRole("button", { name: "Add ingredient" })).toBeEnabled();

  async function receive(name: string, quantity: string, code: string, alpha = "") {
    await inventory.locator('select[name="ingredient_id"]').selectOption({ label: name });
    await inventory.getByLabel("Lot code").fill(code);
    await inventory.getByLabel("Quantity").fill(quantity);
    await inventory.locator('select[name="location_id"]').selectOption({ label: locationName });
    if (alpha) await inventory.getByLabel("Hop lot alpha % (optional)").fill(alpha);
    await Promise.all([
      page.waitForResponse(postedTo("/ingredient-lots")),
      inventory.getByRole("button", { name: "Receive inventory" }).click({ force: true }),
    ]);
    await expect(inventory.getByRole("button", { name: "Receive inventory" })).toBeEnabled();
  }
  await receive(maltName, "10000", `MALT-${stamp}`);
  await receive(hopName, "200", `HOP-${stamp}`, "6.2");
  await receive(yeastName, "2", `YEAST-${stamp}`);

  async function addLine(name: string, amount: string) {
    await page.getByLabel("Recipe ingredient").selectOption({ label: name });
    await page.locator("#line-amount").fill(amount);
    await page.getByRole("button", { name: "Add to recipe" }).click();
  }
  await addLine(maltName, "5000");
  await addLine(hopName, "40");
  await addLine(yeastName, "1");

  await page.getByLabel("Recipe name").fill(recipeName);
  await page.getByLabel("Equipment").selectOption({ label: equipmentName });
  const createResponse = page.waitForResponse((response) =>
    response.url().endsWith("/api/v1/recipe-designs") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Calculate and save version" }).click();
  const original = await (await createResponse).json();
  await expect(page.getByRole("heading", { name: `${recipeName} · v1` })).toBeVisible();
  await expect(page.getByText("AVAILABLE", { exact: true })).toHaveCount(3);
  await expect(page.getByText("OG", { exact: true })).toBeVisible();

  await page.getByLabel("Scale target liters").fill("10");
  await page.getByRole("button", { name: "Clone as scaled new version" }).click();
  await expect(page.getByRole("heading", { name: `${recipeName} · v2` })).toBeVisible();
  const preserved = await page.evaluate(async (versionId) => {
    const response = await fetch(`/api/v1/recipe-designs/${versionId}`);
    return response.json();
  }, original.version_id);
  expect(preserved.version_number).toBe(1);
  expect(Number(preserved.batch_size_liters)).toBe(20);
  expect(preserved.calculations).toEqual(original.calculations);
});
