export const STAGE_SEQUENCE = [
  "PRE_BREW",
  "MASH_IN",
  "MASH",
  "MASH_COMPLETE",
  "BOIL",
  "CHILL_KNOCKOUT",
  "TRANSFER",
  "YEAST_PITCH",
  "BREW_DAY_AUDIT",
] as const;

export type StageCode = (typeof STAGE_SEQUENCE)[number];

export const STAGE_META: Record<
  StageCode,
  { label: string; purpose: string }
> = {
  PRE_BREW: {
    label: "Pre-Brew",
    purpose: "Gather ingredients, heat strike water, and confirm equipment readiness.",
  },
  MASH_IN: {
    label: "Mash-In",
    purpose: "Dough in and stabilize mash temperature.",
  },
  MASH: {
    label: "Mash",
    purpose: "Hold the mash rest. Use a timer if helpful — timers never advance the stage.",
  },
  MASH_COMPLETE: {
    label: "Mash Complete",
    purpose: "Vorlauf / sparge as your system requires and collect wort for the boil.",
  },
  BOIL: {
    label: "Boil",
    purpose: "Boil wort and add hops on schedule. Timers are informational only.",
  },
  CHILL_KNOCKOUT: {
    label: "Chill / Knockout",
    purpose: "Chill wort and capture knockout gravity/temperature when ready.",
  },
  TRANSFER: {
    label: "Transfer",
    purpose: "Transfer wort to the fermenter. Record transferred volume when measured.",
  },
  YEAST_PITCH: {
    label: "Yeast Pitch",
    purpose: "Pitch yeast at a safe temperature and note pitch conditions.",
  },
  BREW_DAY_AUDIT: {
    label: "Brew-Day Audit",
    purpose: "Review completeness, adherence, and planned vs actual before closing.",
  },
};

export function stageLabel(code: string | null | undefined): string {
  if (!code) return "Not started";
  return STAGE_META[code as StageCode]?.label ?? code;
}

export function stagePurpose(code: string | null | undefined): string {
  if (!code) return "";
  return STAGE_META[code as StageCode]?.purpose ?? "";
}
