# ADR-003 — Epic 1 Calculation Formula Methodologies (v1)

## Metadata

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** ADR-002 deferred authoritative brewing formulas until Increment 5. Product Owner authorized this v1 set as Epic 1 calculation authority.

## Decision

Authoritative Epic 1 calculations are identified by stable formula IDs and versions (`formula_id@version`). Changing equation or constant behavior requires a new formula version, updated golden fixtures, and Product Owner approval; historical stored explanations must retain their original formula identity and must not be silently reinterpreted. Every authoritative runtime result exposes `formula_id`, `formula_version`, `source_reference`, `assumptions`, `precision`, and explanation, with `source_reference` matching the Runtime string in the corresponding section below.

## Provenance checklist

| Field | Requirement |
|-------|-------------|
| Formula ID + version | Stable identity (e.g. `OG_ESTIMATE@v1`) |
| Exact algorithm / equation | One canonical definition per formula section |
| Constants | Listed once in that section’s Constants block when applicable |
| Units | Internal conversion targets for the algorithm |
| Assumptions | Explicit; no silent defaults for missing brewing losses |
| Rounding / precision | Per Global rounding policy and each section’s precision |
| Reference / source | Specific enough to re-derive the method; no duplicate citations |

Vague source labels (for example “standard homebrew gravity points method,” “standard infusion equation,” or “conventional brewing factors”) are forbidden in this ADR and in runtime `source_reference` strings.

## Formula catalog

| Formula ID | Version | Section | Exact method | Canonical reference |
|------------|---------|---------|--------------|---------------------|
| `OG_ESTIMATE` | v1 | §A | Gravity points into batch volume | Palmer, *How to Brew*; Daniels, *Designing Great Beers* (PPG) |
| `FG_ESTIMATE` | v1 | §B | Expected apparent attenuation applied to OG | Derived from §C |
| `APPARENT_ATTENUATION` | v1 | §C | SG form of apparent attenuation | SG rearrangement (not ASBC Plato) |
| `ABV` | v1 | §D | ABV from OG and FG | Palmer, *How to Brew* |
| `IBU` | v1 | §E | Tinseth utilization | Tinseth hop-utilization equations |
| `COLOR` | v1 | §F | Morey MCU→SRM | Morey SRM power-fit model |
| `WATER_REQUIREMENTS` | v1 | §G | Mash (+ optional sparge); recorded losses only | BrewingOS compositional definition |
| `STRIKE_TEMP` | v1 | §H | Palmer infusion strike | Palmer, *How to Brew*, infusion mash |
| `RECIPE_SCALING` | v1 | §I | Linear batch-volume scale factor | BrewingOS proportional scaling |
| `UNIT_CONVERSION` | v1 | §J | Fixed mass/volume/temperature factors | NIST Handbook 44 / SI exact factors |

## Principles

1. Results are **ESTIMATED** or **CALCULATED**, never **MEASURED**.
2. Missing required inputs return status `MISSING` (no fabricated authoritative value).
3. Invalid inputs return status `INVALID`.
4. Formula ID and version are returned with every authoritative result.
5. Historical explanations preserve formula identity across future formula versions.
6. Exact equations and constants used in code are documented in this ADR.
7. Formula behavior changes require a new version, updated golden fixtures, and PO approval.

## Global rounding policy

Numeric results use `app.calculations.types.round_decimal`, which applies `Decimal.quantize` at the precision listed in each section (Python `decimal` default rounding mode: **ROUND_HALF_EVEN**).

---

## A. `OG_ESTIMATE` v1 — Gravity points method

### Identity

`OG_ESTIMATE@v1`

### Units

Mass → **lb**; volume → **US gallon**; efficiency → **percent (0–100)**; potential → specific gravity for 1 lb extract in 1 US gal at 100% efficiency. Non-US inputs are converted via §J before this algorithm.

### Constants

| Name | Value / definition |
|------|--------------------|
| Potential points | `(potential_sg − 1) × 1000` |
| Efficiency fraction | `E / 100` |

### Equation / Algorithm

For each fermentable \(i\):

\[
C_i = W_i^{\mathrm{(lb)}} \times ((P_i - 1)\times 1000) \times \frac{E}{100}
\]

\[
\mathrm{OG} = 1 + \frac{\sum_i C_i}{V_{\mathrm{batch}}^{\mathrm{(gal)}} \times 1000}
\]

### Assumptions

- Efficiency is overall brewhouse efficiency into the stated batch volume.
- Result kind is **ESTIMATED**.

### Rounding / Precision

**3** decimal places (SG).

### References

1. John Palmer, *How to Brew* (Brewers Publications) — gravity / points for recipe formulation.
2. Ray Daniels, *Designing Great Beers* (Brewers Publications) — PPG formulation method.

### Runtime `source_reference`

`ADR-003 §A — OG = 1 + Σ(W_lb×(P−1)×1000×E/100) / (V_gal×1000); Palmer/Daniels PPG`

---

## B. `FG_ESTIMATE` v1 — Final gravity from expected apparent attenuation

### Identity

`FG_ESTIMATE@v1`

### Units

OG and FG → **specific gravity**; attenuation \(A\) → **percent**.

### Equation / Algorithm

\[
\mathrm{FG} = 1 + (\mathrm{OG} - 1)\times\left(1 - \frac{A}{100}\right)
\]

### Assumptions

- \(A\) is **expected** apparent attenuation (yeast profile / recipe line), not measured fermentation data.
- When OG comes from `OG_ESTIMATE`, FG remains **ESTIMATED**.
- Algebraically consistent with §C.

### Rounding / Precision

**3** decimal places (SG).

### References

1. Derived from §C; yeast attenuation ranges are manufacturer data when supplied on the recipe line.

### Runtime `source_reference`

`ADR-003 §B — FG = 1+(OG−1)×(1−A/100); derived from apparent attenuation`

---

## C. `APPARENT_ATTENUATION` v1

### Identity

`APPARENT_ATTENUATION@v1`

### Units

OG and FG → **specific gravity**; result → **percent**.

### Equation / Algorithm

\[
\mathrm{AA\%} = \frac{\mathrm{OG} - \mathrm{FG}}{\mathrm{OG} - 1} \times 100
\]

### Assumptions

- SG-based form only; not the ASBC Plato-based formula (`APPARENT_ATTENUATION@v2` if required later).
- Requires \(\mathrm{OG} > 1\); otherwise `INVALID`.

### Rounding / Precision

**1** decimal place.

### References

1. John Palmer, *How to Brew* (Brewers Publications) — attenuation discussion (SG rearrangement used here).

### Runtime `source_reference`

`ADR-003 §C — AA% = ((OG−FG)/(OG−1))×100 (SG form; not ASBC Plato)`

---

## D. `ABV` v1

### Identity

`ABV@v1`

### Units

OG and FG → **specific gravity**; result → **% ABV**.

### Constants

| Name | Value | Meaning |
|------|-------|---------|
| Homebrew ABV factor | `131.25` | SG difference → % ABV |

### Equation / Algorithm

\[
\mathrm{ABV\%} = (\mathrm{OG} - \mathrm{FG}) \times 131.25
\]

### Assumptions

- Simplified homebrew approximation only (not Balling / high-gravity models; those would be `ABV@v2+`).
- Kind is **CALCULATED** when both gravities are supplied to this formula (upstream values may still be estimates).

### Rounding / Precision

**2** decimal places.

### References

1. John Palmer, *How to Brew* (Brewers Publications) — homebrew ABV approximation.

### Runtime `source_reference`

`ADR-003 §D — ABV% = (OG−FG)×131.25; Palmer How to Brew approx.`

---

## E. `IBU` v1 — Tinseth

### Identity

`IBU@v1`

### Units

Hop mass → **grams**; wort volume → **liters**; alpha acid → **percent**; time → **minutes**; boil gravity → **SG**.

### Constants

| Name | Value | Role |
|------|-------|------|
| Bigness base | `1.65` | BF scale |
| Gravity-term base | `0.000125` | BF gravity exponent base |
| Boil-time decay | `0.04` | Per-minute factor in \(e^{-0.04 t}\) |
| Boil-time divisor | `4.15` | BTF denominator |

### Equation / Algorithm

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
\mathrm{IBU}_i = U \times (\mathrm{mg\,\alpha/L})_i,\qquad
\mathrm{IBU} = \sum_i \mathrm{IBU}_i
\]

Stage policy: `BOIL`, `FIRST_WORT`, `WHIRLPOOL`, and `MASH` use Tinseth with supplied `time_minutes`; `DRY_HOP` contributes **0 IBU**.

### Assumptions

- No pellet utilization multiplier in v1.
- Batch volume is the post-boil volume proxy for mg/L when a separate post-boil volume is unavailable (recorded on the result).
- Result kind is **ESTIMATED**.

### Rounding / Precision

Total IBU → **1** decimal place.

### References

1. Glenn Tinseth — hop utilization / bitterness equations (Tinseth model), historically published via the Real Beer hop pages / Tinseth hop utilization write-up; constants above match the common software reproduction of that model.

### Runtime `source_reference`

`ADR-003 §E — Tinseth: U=1.65·0.000125^(Gb−1)·(1−e^(−0.04t))/4.15; dry-hop=0; no pellet factor`

---

## F. `COLOR` v1 — Morey SRM

### Identity

`COLOR@v1`

### Units

Mass → **lb**; volume → **US gallon**; color → **°Lovibond**; result → **SRM**.

### Constants

| Name | Value | Role |
|------|-------|------|
| Morey scale | `1.4922` | SRM scale factor |
| Morey exponent | `0.6859` | MCU power |

### Equation / Algorithm

\[
\mathrm{MCU} = \sum_i \frac{W_i^{\mathrm{(lb)}} \times L_i}{V_{\mathrm{batch}}^{\mathrm{(gal)}}}
\]

\[
\mathrm{SRM} = 1.4922 \times \mathrm{MCU}^{0.6859}
\]

### Assumptions

- Color inputs are °Lovibond (or treated as such on recipe/ingredient snapshots).
- Morey power-fit only (not Mosher / Daniels color models).
- Result kind is **ESTIMATED**.

### Rounding / Precision

**1** decimal place (SRM).

### References

1. Dan Morey — MCU→SRM power-fit model, commonly cited in homebrew formulation references including Palmer, *How to Brew*.

### Runtime `source_reference`

`ADR-003 §F — Morey: SRM = 1.4922 × MCU^0.6859; MCU = Σ(W_lb×°L)/V_gal`

---

## G. `WATER_REQUIREMENTS` v1

### Identity

`WATER_REQUIREMENTS@v1`

### Units

Volumes in the caller’s unit after §J conversion when needed; totals reported in the requested output unit.

### Equation / Algorithm

\[
V_{\mathrm{total}} = V_{\mathrm{mash}} + V_{\mathrm{sparge}}
\]

\(V_{\mathrm{total}}\) in this formula means mash plus sparge water recorded for the recipe; it is not a full loss-adjusted liquor requirement unless those additional values are separately available.

\(V_{\mathrm{sparge}}\) is included only when recorded. Boil-off and trub are reported when recorded; otherwise **`NOT RECORDED`** (never defaulted).

Related helpers (same formula identity family):

- Trub recorded: \(V_{\mathrm{post}} = V_{\mathrm{batch}} + V_{\mathrm{trub}}\); else \(V_{\mathrm{post}} \approx V_{\mathrm{batch}}\) with assumption noted on the result.
- Boil-off recorded: \(V_{\mathrm{pre}} = V_{\mathrm{post}} + V_{\mathrm{boil-off}}\); else pre-boil is `MISSING`.

### Assumptions

- No silent default boil-off rate, grain absorption, or trub loss.
- Sparge is optional; mash water is required for \(V_{\mathrm{total}}\).
- Epic 1 excludes full water-chemistry / residual-alkalinity laboratory models.

### Rounding / Precision

Volume totals → **3** decimal places in the output unit.

### References

1. BrewingOS ADR-003 compositional water accounting (Epic 1 scope).

### Runtime `source_reference`

`ADR-003 §G — V_total = V_mash + V_sparge(optional); losses NOT RECORDED if absent`

---

## H. `STRIKE_TEMP` v1 — Palmer infusion strike

### Identity

`STRIKE_TEMP@v1`

### Units

Water/grain ratio \(r\) in **US quarts water per pound grain**. Temperatures are computed in **°F**, then converted to **°C** for output.

### Constants

| Name | Value | Role |
|------|-------|------|
| Grain thermal factor | `0.2` | Valid with \(r\) in qt/lb and temperatures in °F |

### Equation / Algorithm

\[
r = \frac{V_{\mathrm{water}}^{\mathrm{(qt)}}}{W_{\mathrm{grain}}^{\mathrm{(lb)}}}
\]

\[
T_w^{\mathrm{(°F)}} = \frac{0.2}{r}\,(T_{\mathrm{mash}}^{\mathrm{(°F)}} - T_{\mathrm{grain}}^{\mathrm{(°F)}}) + T_{\mathrm{mash}}^{\mathrm{(°F)}}
\]

### Assumptions

- Single-infusion mash only (no decoction / multi-infusion in v1).
- Grain and mash target temperatures are required inputs (missing → `MISSING`; no implied room-temperature grain default).
- Result kind is **ESTIMATED**.

### Rounding / Precision

Strike temperature → **1** decimal place (°C).

### References

1. John Palmer, *How to Brew* (Brewers Publications) — infusion mash strike-water temperature equation.

### Runtime `source_reference`

`ADR-003 §H — Palmer: Tw°F = (0.2/r)(Tmash−Tgrain)+Tmash; r = qt water / lb grain`

---

## I. `RECIPE_SCALING` v1

### Identity

`RECIPE_SCALING@v1`

### Units

Batch sizes converted to **US gallons** before the scale factor; ingredient amounts scaled in their native units.

### Equation / Algorithm

\[
f = \frac{V_{\mathrm{to}}^{\mathrm{(gal)}}}{V_{\mathrm{from}}^{\mathrm{(gal)}}}
\]

\[
a'_i = a_i \times f
\]

### Assumptions

- Linear mass/volume scaling only.
- Does not re-fit hop utilization, efficiency, or boil-off for the new size in v1.
- Does not mutate a RecipeVersion; persistence requires a new version per recipe rules.

### Rounding / Precision

Scale factor → **6** decimal places; scaled amounts → **4** decimal places.

### References

1. BrewingOS ADR-003 proportional scaling definition.

### Runtime `source_reference`

`ADR-003 §I — scale factor f = V_to_gal / V_from_gal; a′ = a×f (linear)`

---

## J. `UNIT_CONVERSION` v1

### Identity

`UNIT_CONVERSION@v1`

### Units

Mass, volume, and temperature unit pairs supported by the conversion tables below.

### Constants

| Conversion | Factor | Note |
|------------|--------|------|
| `lb` → `g` | `453.59237` | avoirdupois pound, exact |
| `oz` → `g` | `28.349523125` | avoirdupois ounce, exact |
| `kg` → `g` | `1000` | SI |
| `gal` (US) → `ml` | `3785.411784` | US gallon, exact |
| `qt` (US) → `ml` | `946.352946` | US quart |
| `L` → `ml` | `1000` | SI |
| °C ↔ °F | \(F = C\times 9/5 + 32\); \(C = (F-32)\times 5/9\) | linear |

### Equation / Algorithm

Convert via a common base unit (grams for mass, milliliters for volume) using the factors above; apply the °C/°F relations for temperature.

### Assumptions

- `gal` / `qt` mean **US** liquid measures (not Imperial).
- Unsupported unit pairs → `INVALID` (no guessed factors).

### Rounding / Precision

Converted numeric results → **6** decimal places.

### References

1. NIST Handbook 44 / SI — avoirdupois pound and ounce to gram (exact).
2. US gallon = \(231\ \mathrm{in}^3 = 3.785411784\ \mathrm{L}\) (exact).
3. Standard linear °C/°F relation.

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

1. Calculation modules must keep `source_reference` aligned with this ADR’s Runtime strings.
2. Epic 1 treats §§A–J as the auditable calculation foundation.
