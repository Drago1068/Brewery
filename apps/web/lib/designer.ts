export type Ingredient = {
  id: string;
  name: string;
  category: string;
  canonical_unit: "g" | "L" | "each";
};

export type DraftLine = {
  ingredient_id: string;
  amount: string;
  unit: "g" | "L" | "each";
  use_stage: string;
  timing_minutes?: number;
};

export function defaultStage(category: string): string {
  if (category === "FERMENTABLE") return "MASH";
  if (category === "HOP") return "BOIL";
  if (category === "YEAST") return "FERMENTATION";
  if (category === "WATER_ADDITION") return "MASH";
  return "MISCELLANEOUS";
}

export function makeDraftLine(
  ingredient: Ingredient,
  amount: string,
  timing?: number,
): DraftLine {
  return {
    ingredient_id: ingredient.id,
    amount,
    unit: ingredient.canonical_unit,
    use_stage: defaultStage(ingredient.category),
    ...(ingredient.category === "HOP" ? { timing_minutes: timing ?? 60 } : {}),
  };
}

export function displayEstimate(value: string | undefined, places: number): string {
  if (value === undefined || value === "") return "Not calculated";
  return Number(value).toFixed(places);
}
