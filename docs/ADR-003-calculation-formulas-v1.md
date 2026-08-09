# ADR-003 — Epic 1 Calculation Formula Methodologies (v1)

**Status:** Accepted (provenance strengthened 2026-08-09 for final Epic 1 acceptance)  
**Date:** 2026-08-09  
**Context:** ADR-002 deferred authoritative brewing formulas until Increment 5. Product Owner authorized proceeding with Increment 5, accepting the v1 set below. Independent review required **stronger provenance** (exact equations, constants, units, assumptions, rounding, and specific references) **without changing formula behavior**.

## Decision

Authoritative Epic 1 calculations use the following **formula identities**. Changing behavior later requires a new formula version plus golden-fixture updates (handoff §34).

Runtime results expose `formula_id`, `formula_version`, `source_reference`, `assumptions`, `precision`, and explanation. The `source_reference` string for each module points to the matching section of this ADR.

### Provenance checklist (every authoritative formula)

Each §A–§J section documents:

| Field | Requirement |
|-------|-------------|
| Formula ID + version | Stable identity (e.g. `OG_ESTIMATE@v1`) |
| Exact algorithm / equation | Reproducible math as implemented |
| Constants | Numeric factors used in code |
| Units | Internal conversion targets |
| Assumptions | Explicit; no silent defaults for missing brewing losses |
| Rounding / precision | Decimal places via `Decimal.quantize` (Python default half-even) |
| Reference / source | Specific enough to re-derive the method |

---

## Formula catalog (summary)

| Formula ID | Version | Exact method (short) | Canonical reference |
|------------|---------|----------------------|---------------------|
| `OG_ESTIMATE` | v1 | §A gravity points into batch volume | Palmer, *How to Brew*; Daniels, *Designing Great Beers* (PPG method) |
| `FG_ESTIMATE` | v1 | §B attenuation applied to OG | Derived from §C definition of apparent attenuation |
| `ABV` | v1 | §D `(OG − FG) × 131.25` | Palmer, *How to Brew* (homebrew ABV approximation) |
| `APPARENT_ATTENUATION` | v1 | §C SG form of AA% | SG rearrangement of apparent attenuation (not ASBC Plato) |
| `IBU` | v1 | §E Tinseth utilization | Tinseth hop-utilization equations (constants below) |
| `COLOR` | v1 | §F Morey MCU→SRM | Morey SRM model (MCU power fit; constants below) |
| `WATER_REQUIREMENTS` | v1 | §G recorded mash/sparge (+ optional losses) | BrewingOS ADR-003 compositional definition |
| `STRIKE_TEMP` | v1 | §H Palmer infusion strike | Palmer, *How to Brew*, infusion mash (`0.2` factor) |
| `RECIPE_SCALING` | v1 | §I linear volume scale factor | BrewingOS ADR-003 proportional scaling |
| `UNIT_CONVERSION` | v1 | §J fixed conversion constants | NIST Handbook 44 / SI exact factors |

---

## Principles

1. Results are **ESTIMATED** / **CALCULATED**, never **MEASURED**.
2. Missing required inputs → status `MISSING` (no fabricated authoritative value).
3. Invalid inputs → status `INVALID`.
4. Formula id + version are returned with every authoritative result.
5. Historical stored explanations must retain formula identity; future formula changes do not rewrite history.
6. Provenance must state the **exact equation and constants** used in code — not only a marketing name.
7. Vague labels (e.g. “standard homebrew gravity points method,” “standard infusion equation,” “conventional brewing factors”) are **forbidden** in ADR text and runtime `source_reference`.

### Global rounding policy

Unless a section states otherwise, numeric results use `app.calculations.types.round_decimal` → `Decimal.quantize` at the listed precision (Python `decimal` default rounding mode: **ROUND_HALF_EVEN**).

---

## A. `OG_ESTIMATE` v1 — Gravity points method

**Identity:** `OG_ESTIMATE@v1`

### Units (internal)

Mass → **lb**; volume → **US gallon**; efficiency → **percent 0–100**; potential → specific gravity of 1 lb extract in 1 US gal at 100% efficiency (e.g. `1.037`).

### Constants / definitions

- `potential_points = (potential_sg − 1) × 1000`
- Efficiency applied as `E/100` (percent → fraction)

### Equation

For each fermentable \(i\):

\[
C_i = W_i^{\mathrm{(lb)}} \times ((P_i - 1)\times 1000) \times \frac{E}{100}
\]

\[
\mathrm{OG} = 1 + \frac{\sum_i C_i}{V_{\mathrm{batch}}^{\mathrm{(gal)}} \times 1000}
\]

### Assumptions

- Brewhouse efficiency is a single recipe-level percent applied equally to all fermentable lines.
- `potential_sg` is the ingredient’s extract potential as PPG-style SG (not Plato).
- Metric mass/volume inputs are converted to lb / US gal before the equation (via §J).
- Result kind is **ESTIMATED**.

### Rounding / precision

**3** decimal places (SG), e.g. `1.056`.

### References

1. John Palmer, *How to Brew* (Brewers Publications) — gravity / points discussion for recipe formulation.  
2. Ray Daniels, *Designing Great Beers* (Brewers Publications) — points-per-pound-per-gallon (PPG) formulation method consistent with the equations above.

### Runtime `source_reference`

`ADR-003 §A — OG = 1 + Σ(W_lb×(P−1)×1000×E/100) / (V_gal×1000); Palmer/Daniels PPG`

---

## B. `FG_ESTIMATE` v1 — Final gravity from expected apparent attenuation

**Identity:** `FG_ESTIMATE@v1`

### Units

OG, FG → **specific gravity**; attenuation \(A\) → **percent**.

### Equation

\[
\mathrm{FG} = 1 + (\mathrm{OG} - 1)\times\left(1 - \frac{A}{100}\right)
\]

### Assumptions

- Uses **expected** apparent attenuation (yeast profile / recipe line), not measured fermentation data.
- OG may itself be estimated (`OG_ESTIMATE`); FG remains **ESTIMATED**.
- Algebraically consistent with §C.

### Rounding / precision

**3** decimal places (SG).

### References

Derived algebraically from §C. Yeast attenuation ranges are manufacturer data when supplied on the recipe line.

### Runtime `source_reference`

`ADR-003 §B — FG = 1+(OG−1)×(1−A/100); derived from apparent attenuation`

---

## C. `APPARENT_ATTENUATION` v1

**Identity:** `APPARENT_ATTENUATION@v1`

### Units

OG, FG → **specific gravity**; result → **percent**.

### Equation (specific-gravity form)

\[
\mathrm{AA\%} = \frac{\mathrm{OG} - \mathrm{FG}}{\mathrm{OG} - 1} \times 100
\]

### Assumptions

- SG-based homebrew form only.
- **Not** the ASBC Plato-based apparent attenuation formula (`APPARENT_ATTENUATION@v2` if needed later).
- Requires \(\mathrm{OG} > 1\); otherwise `INVALID`.

### Rounding / precision

**1** decimal place.

### References

Standard rearrangement of apparent attenuation when gravity is expressed as specific gravity. Cross-check: Palmer, *How to Brew*, attenuation discussion.

### Runtime `source_reference`

`ADR-003 §C — AA% = ((OG−FG)/(OG−1))×100 (SG form; not ASBC Plato)`

---

## D. `ABV` v1

**Identity:** `ABV@v1`

### Units

OG, FG → **specific gravity**; result → **% ABV**.

### Equation

\[
\mathrm{ABV\%} = (\mathrm{OG} - \mathrm{FG}) \times 131.25
\]

**Constant:** `131.25` (SG→%ABV factor).

### Assumptions

- Simplified homebrew ABV approximation only.
- **Not** Balling / high-gravity alternate ABV models (`ABV@v2+`).
- Kind is **CALCULATED** when both gravities are provided to the formula (inputs may still be estimates upstream).

### Rounding / precision

**2** decimal places.

### References

1. John Palmer, *How to Brew* (Brewers Publications) — documents \(\mathrm{ABV} \approx (\mathrm{OG}-\mathrm{FG})\times 131.25\).

### Runtime `source_reference`

`ADR-003 §D — ABV% = (OG−FG)×131.25; Palmer How to Brew approx.`

---

## E. `IBU` v1 — Tinseth

**Identity:** `IBU@v1`

### Units (internal)

Hop mass → **grams**; wort volume → **liters**; alpha acid → **percent**; time → **minutes**; boil gravity → **SG**.

### Constants (Tinseth)

| Constant | Value | Role |
|----------|-------|------|
| Bigness base | `1.65` | BF scale |
| Gravity term base | `0.000125` | \(\mathrm{BF}\) gravity exponent base |
| Boil-time decay | `0.04` | per minute in \(e^{-0.04 t}\) |
| Boil-time divisor | `4.15` | BTF denominator |

### Equations

\[
\mathrm{BF} = 1.65 \times 0.000125^{(G_b - 1)}
\]

\[
\mathrm{BTF} = \frac{1 - e^{-0.04\,t}}{4.15}
\]

\[
U = \mathrm{BF} \times \mathrm{BTF}
\]

\[
\mathrm{mg\,\alpha/L} = \frac{(\alpha/100)\times m_{\mathrm{hop}}^{\mathrm{(g)}} \times 1000}{V^{\mathrm{(L)}}}
\]

\[
\mathrm{IBU}_i = U \times (\mathrm{mg\,\alpha/L})_i;\quad \mathrm{IBU} = \sum_i \mathrm{IBU}_i
\]

### Stage policy (v1)

| Stage | Contribution |
|-------|--------------|
| `BOIL`, `FIRST_WORT`, `WHIRLPOOL`, `MASH` | Tinseth with supplied `time_minutes` |
| `DRY_HOP` | **0 IBU** (explicit; not estimated) |

### Assumptions

- No pellet utilization multiplier in v1.
- Batch volume is used as the post-boil volume **proxy** for mg/L when a separate post-boil volume is unavailable (recorded on the result).
- Dry-hop contributes exactly 0 IBU (not an estimated utilization).
- Result kind is **ESTIMATED**.

### Rounding / precision

Total IBU → **1** decimal place.

### References

1. Glenn Tinseth — hop utilization / bitterness equations (Tinseth model), historically published via the Real Beer hop pages / Tinseth hop utilization write-up; constants above match the common software reproduction of that model.

### Runtime `source_reference`

`ADR-003 §E — Tinseth: U=1.65·0.000125^(Gb−1)·(1−e^(−0.04t))/4.15; dry-hop=0; no pellet factor`

---

## F. `COLOR` v1 — Morey SRM

**Identity:** `COLOR@v1`

### Units (internal)

Mass → **lb**; volume → **US gallon**; color → **°Lovibond**; result → **SRM**.

### Equations

\[
\mathrm{MCU} = \sum_i \frac{W_i^{\mathrm{(lb)}} \times L_i}{V_{\mathrm{batch}}^{\mathrm{(gal)}}}
\]

\[
\mathrm{SRM} = 1.4922 \times \mathrm{MCU}^{0.6859}
\]

**Constants:** `1.4922`, exponent `0.6859`.

### Assumptions

- Color inputs are °Lovibond (or treated as such when stored on recipe/ingredient snapshots).
- Morey power-fit only (not Mosher / Daniels alternate color models).
- Result kind is **ESTIMATED**.

### Rounding / precision

**1** decimal place (SRM).

### References

1. Dan Morey — MCU→SRM power-fit model (constants `1.4922`, `0.6859`), as commonly cited in homebrew formulation references including Palmer, *How to Brew*.

### Runtime `source_reference`

`ADR-003 §F — Morey: SRM = 1.4922 × MCU^0.6859; MCU = Σ(W_lb×°L)/V_gal`

---

## G. `WATER_REQUIREMENTS` v1

**Identity:** `WATER_REQUIREMENTS@v1`

### Units

Volumes in the caller’s unit after conversion via §J when needed; totals reported in the requested output unit.

### Equations (compositional — no invented losses)

\[
V_{\mathrm{total}} = V_{\mathrm{mash}} + V_{\mathrm{sparge}}
\]

where \(V_{\mathrm{sparge}}\) is included **only if recorded**.

Boil-off and trub loss are **reported when recorded**; otherwise explicitly **`NOT RECORDED`** — never defaulted.

Related volume helpers (same formula id family):

- If trub recorded: \(V_{\mathrm{post}} = V_{\mathrm{batch}} + V_{\mathrm{trub}}\); else \(V_{\mathrm{post}} \approx V_{\mathrm{batch}}\) with assumption noted.
- If boil-off recorded: \(V_{\mathrm{pre}} = V_{\mathrm{post}} + V_{\mathrm{boil\text{-}off}}\); else pre-boil is `MISSING`.

### Assumptions

- No silent default boil-off rate, grain absorption, or trub loss.
- Sparge is optional; mash water is required for a total.
- Epic 1 excludes full water-chemistry / residual-alkalinity laboratory models.

### Rounding / precision

Volume totals → **3** decimal places in the output unit.

### References

BrewingOS ADR-003 compositional water accounting (deliberate Epic 1 scope).

### Runtime `source_reference`

`ADR-003 §G — V_total = V_mash + V_sparge(optional); losses NOT RECORDED if absent`

---

## H. `STRIKE_TEMP` v1 — Palmer infusion strike

**Identity:** `STRIKE_TEMP@v1`

### Units

Water/grain ratio \(r\) in **US quarts water per pound grain**. Temperatures computed in **°F**, then converted to **°C** for output.

### Constant

Grain thermal factor: **`0.2`** (valid with \(r\) in qt/lb and temperatures in °F per Palmer).

### Equation

\[
r = \frac{V_{\mathrm{water}}^{\mathrm{(qt)}}}{W_{\mathrm{grain}}^{\mathrm{(lb)}}}
\]

\[
T_w^{\mathrm{(°F)}} = \frac{0.2}{r}\,(T_{\mathrm{mash}}^{\mathrm{(°F)}} - T_{\mathrm{grain}}^{\mathrm{(°F)}}) + T_{\mathrm{mash}}^{\mathrm{(°F)}}
\]

### Assumptions

- Single-infusion mash; no decoction / multi-infusion stepping in v1.
- Grain and mash target temperatures are required inputs (no assumed room-temp grain default when missing → `MISSING`).
- Factor `0.2` applies only with qt/lb and °F as above.

### Rounding / precision

Strike temperature output → **1** decimal place (°C).

### References

1. John Palmer, *How to Brew* (Brewers Publications) — infusion mash strike-water temperature equation with factor `0.2` for qt/lb / °F.

### Runtime `source_reference`

`ADR-003 §H — Palmer: Tw°F = (0.2/r)(Tmash−Tgrain)+Tmash; r = qt water / lb grain`

---

## I. `RECIPE_SCALING` v1

**Identity:** `RECIPE_SCALING@v1`

### Units

Batch sizes converted to **US gallons** before the scale factor; ingredient amounts scaled in their native units.

### Equation

\[
f = \frac{V_{\mathrm{to}}^{\mathrm{(gal)}}}{V_{\mathrm{from}}^{\mathrm{(gal)}}};\quad a'_i = a_i \times f
\]

### Assumptions

- Linear mass/volume scaling only.
- Does **not** re-fit hop utilization, efficiency, or boil-off for the new size in v1.
- Does **not** mutate a RecipeVersion; persistence requires a new version per recipe rules.

### Rounding / precision

Scale factor → **6** decimal places; scaled amounts → **4** decimal places.

### References

BrewingOS ADR-003 proportional scaling definition.

### Runtime `source_reference`

`ADR-003 §I — scale factor f = V_to_gal / V_from_gal; a′ = a×f (linear)`

---

## J. `UNIT_CONVERSION` v1

**Identity:** `UNIT_CONVERSION@v1`

### Exact constants used in code

| Conversion | Factor | Note |
|------------|--------|------|
| `lb` → `g` | `453.59237` | avoirdupois pound, exact |
| `oz` → `g` | `28.349523125` | avoirdupois ounce, exact |
| `kg` → `g` | `1000` | SI |
| `gal` (US) → `ml` | `3785.411784` | US gallon, exact |
| `qt` (US) → `ml` | `946.352946` | US quart |
| `L` → `ml` | `1000` | SI |
| °C ↔ °F | \(F = C\times 9/5 + 32\); \(C = (F-32)\times 5/9\) | linear |

### Assumptions

- `gal` / `qt` mean **US** customary liquid measures (not Imperial).
- Unsupported unit pairs → `INVALID` (no guessed factors).

### Rounding / precision

Converted numeric results → **6** decimal places.

### References

1. NIST Handbook 44 / SI conversion — avoirdupois pound and ounce to gram (exact).  
2. US gallon = \(231\ \mathrm{in}^3 = 3.785411784\ \mathrm{L}\) (exact).  
3. Temperature — standard linear °C/°F relation.

### Runtime `source_reference`

`ADR-003 §J — NIST factors: lb=453.59237 g; oz=28.349523125 g; US gal=3.785411784 L`

---

## Non-goals (v1)

- Rager / Garetz IBU models (`IBU@v2+`)
- ASBC Plato apparent attenuation (`APPARENT_ATTENUATION@v2`)
- Advanced water chemistry / residual alkalinity laboratory
- Yeast viability / cell-count pitching rate
- AI-authored calculations
- High-gravity alternate ABV equations (`ABV@v2+`)

## Consequences

1. Calculation modules must keep `source_reference` aligned with this ADR’s section strings.  
2. Formula **numeric behavior** is unchanged by the 2026-08-09 provenance strengthening.  
3. Any future equation/constant change requires a new formula version, updated fixtures, and PO approval.  
4. Epic 1 final acceptance treats §§A–J as the auditable calculation foundation.
