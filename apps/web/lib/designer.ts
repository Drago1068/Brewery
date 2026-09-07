export type CanonicalUnit = "g" | "L" | "each";

export const CANONICAL_UNITS: readonly CanonicalUnit[] = ["g", "L", "each"];

export const USE_STAGES = [
  "MASH",
  "FIRST_WORT",
  "BOIL",
  "WHIRLPOOL",
  "DRY_HOP",
  "FERMENTATION",
  "PACKAGING",
  "MISCELLANEOUS",
] as const;

export type UseStage = (typeof USE_STAGES)[number];

export type Ingredient = {
  id: string;
  name: string;
  category: string;
  canonical_unit: CanonicalUnit;
};

export type DraftLine = {
  ingredient_id: string;
  amount: string;
  unit: CanonicalUnit;
  use_stage: UseStage;
  timing_minutes?: number;
};

export type MashStepDraft = {
  name: string;
  duration_minutes: string;
  temperature_c: string;
};

export type ProcessStepPayload = {
  step_type: "MASH" | "BOIL";
  sequence: number;
  name: string;
  duration_minutes: number | null;
  temperature_c: string | null;
};

export type LinePatch = {
  amount?: string;
  unit?: string;
  use_stage?: string;
  timing_minutes?: number | null;
};

export function defaultStage(category: string): UseStage {
  if (category === "FERMENTABLE") return "MASH";
  if (category === "HOP") return "BOIL";
  if (category === "YEAST") return "FERMENTATION";
  if (category === "WATER_ADDITION") return "MASH";
  return "MISCELLANEOUS";
}

export function isUseStage(value: string): value is UseStage {
  return (USE_STAGES as readonly string[]).includes(value);
}

export function allowedUnits(ingredient: Ingredient): CanonicalUnit[] {
  return [ingredient.canonical_unit];
}

export function stageAllowsTiming(stage: string): boolean {
  return stage === "BOIL" || stage === "MASH" || stage === "WHIRLPOOL" || stage === "DRY_HOP";
}

export function stageRequiresTiming(stage: string): boolean {
  return stage === "BOIL";
}

export function parsePositiveAmount(raw: string): string | undefined {
  const trimmed = raw.trim();
  if (!/^(?:0|[1-9]\d{0,9})(?:\.\d{1,4})?$/.test(trimmed)) return undefined;
  if (/^0(?:\.0+)?$/.test(trimmed)) return undefined;
  return trimmed;
}

export function parseTimingMinutes(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!/^(?:0|[1-9]\d{0,4})$/.test(trimmed)) return undefined;
  const value = Number.parseInt(trimmed, 10);
  if (value < 0 || value > 10080) return undefined;
  return value;
}

export function makeDraftLine(
  ingredient: Ingredient,
  amount: string,
  timing?: number,
): DraftLine {
  const use_stage = defaultStage(ingredient.category);
  const line: DraftLine = {
    ingredient_id: ingredient.id,
    amount,
    unit: ingredient.canonical_unit,
    use_stage,
  };
  if (stageRequiresTiming(use_stage)) {
    line.timing_minutes = timing ?? 60;
  } else if (stageAllowsTiming(use_stage) && timing !== undefined) {
    line.timing_minutes = timing;
  }
  return line;
}

function timingForStage(
  stage: UseStage,
  timing: number | null | undefined,
  previous: number | undefined,
  stageChanged: boolean,
): { timing_minutes?: number; error?: string } {
  if (!stageAllowsTiming(stage)) {
    return {};
  }
  let resolved: number | undefined;
  if (timing === undefined) {
    resolved = stageChanged ? undefined : previous;
  } else if (timing === null) {
    resolved = undefined;
  } else {
    resolved = timing;
  }
  if (resolved === undefined) {
    if (stageRequiresTiming(stage)) {
      return { error: "Boil additions require non-negative timing in minutes." };
    }
    return {};
  }
  if (!Number.isInteger(resolved) || resolved < 0 || resolved > 10080) {
    return { error: "Timing must be a whole number of minutes from 0 to 10080." };
  }
  return { timing_minutes: resolved };
}

export function applyLinePatch(
  line: DraftLine,
  ingredient: Ingredient | undefined,
  patch: LinePatch,
): { line: DraftLine; error?: string } {
  const amountRaw = patch.amount ?? line.amount;
  const amount = parsePositiveAmount(amountRaw);
  if (amount === undefined) {
    return { line, error: "Amount must be a positive number with up to 4 decimal places." };
  }
  const unitRaw = patch.unit ?? line.unit;
  if (!CANONICAL_UNITS.includes(unitRaw as CanonicalUnit)) {
    return { line, error: "Unit is not in the canonical brewing vocabulary." };
  }
  const unit = unitRaw as CanonicalUnit;
  if (ingredient && !allowedUnits(ingredient).includes(unit)) {
    return {
      line,
      error: `Unit must be the ingredient canonical unit (${ingredient.canonical_unit}).`,
    };
  }
  const stageRaw = patch.use_stage ?? line.use_stage;
  if (!isUseStage(stageRaw)) {
    return { line, error: "Stage is not an allowed recipe addition stage." };
  }
  const stageChanged = patch.use_stage !== undefined && patch.use_stage !== line.use_stage;
  const timingResult = timingForStage(
    stageRaw,
    patch.timing_minutes,
    line.timing_minutes,
    stageChanged,
  );
  if (timingResult.error) {
    return { line, error: timingResult.error };
  }
  const next: DraftLine = {
    ingredient_id: line.ingredient_id,
    amount,
    unit,
    use_stage: stageRaw,
  };
  if (timingResult.timing_minutes !== undefined) {
    next.timing_minutes = timingResult.timing_minutes;
  }
  return { line: next };
}

export function defaultMashStep(): MashStepDraft {
  return { name: "Saccharification", duration_minutes: "60", temperature_c: "66.67" };
}

export function addMashStep(
  steps: MashStepDraft[],
  step: MashStepDraft = defaultMashStep(),
): MashStepDraft[] {
  return [...steps, step];
}

export function editMashStep(
  steps: MashStepDraft[],
  index: number,
  patch: Partial<MashStepDraft>,
): MashStepDraft[] {
  return steps.map((step, stepIndex) => (stepIndex === index ? { ...step, ...patch } : step));
}

export function removeMashStep(steps: MashStepDraft[], index: number): MashStepDraft[] {
  return steps.filter((_, stepIndex) => stepIndex !== index);
}

export function orderMashSteps(
  steps: MashStepDraft[],
  fromIndex: number,
  toIndex: number,
): MashStepDraft[] {
  if (
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= steps.length ||
    toIndex >= steps.length ||
    fromIndex === toIndex
  ) {
    return steps;
  }
  const next = [...steps];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

function parseOptionalNonNegativeInt(raw: string): number | null | undefined {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  if (!/^(?:0|[1-9]\d{0,8})$/.test(trimmed)) return undefined;
  return Number.parseInt(trimmed, 10);
}

function parseOptionalDecimal(raw: string): string | null | undefined {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  if (!/^-?(?:0|[1-9]\d{0,6})(?:\.\d{1,3})?$/.test(trimmed)) return undefined;
  return trimmed;
}

export function mashStepError(step: MashStepDraft): string | undefined {
  if (!step.name.trim()) return "Mash step name is required.";
  if (parseOptionalNonNegativeInt(step.duration_minutes) === undefined) {
    return "Mash step duration must be empty or a non-negative whole number of minutes.";
  }
  if (parseOptionalDecimal(step.temperature_c) === undefined) {
    return "Mash step temperature must be empty or a numeric value in °C.";
  }
  return undefined;
}

export function toProcessSteps(
  mashSteps: MashStepDraft[],
  boilDurationMinutes: string,
): { steps?: ProcessStepPayload[]; error?: string } {
  for (const step of mashSteps) {
    const error = mashStepError(step);
    if (error) return { error };
  }
  const boil = parseOptionalNonNegativeInt(boilDurationMinutes);
  if (boil === undefined || boil === null) {
    return { error: "Boil duration must be a non-negative whole number of minutes." };
  }
  const steps: ProcessStepPayload[] = mashSteps.map((step, index) => ({
    step_type: "MASH",
    sequence: index + 1,
    name: step.name.trim(),
    duration_minutes: parseOptionalNonNegativeInt(step.duration_minutes) ?? null,
    temperature_c: parseOptionalDecimal(step.temperature_c) ?? null,
  }));
  steps.push({
    step_type: "BOIL",
    sequence: steps.length + 1,
    name: "Boil",
    duration_minutes: boil,
    temperature_c: null,
  });
  return { steps };
}

export function displayEstimate(value: string | undefined, places: number): string {
  if (value === undefined || value === "") return "Not calculated";
  return Number(value).toFixed(places);
}
