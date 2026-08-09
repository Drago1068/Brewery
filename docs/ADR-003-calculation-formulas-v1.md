# ADR-003 — Epic 1 Calculation Formula Methodologies (v1)

**Status:** Accepted  
**Date:** 2026-08-09  
**Context:** ADR-002 deferred authoritative brewing formulas until Increment 5. Product Owner authorized the v1 set below as Epic 1 calculation authority.

## Decision

Authoritative Epic 1 calculations use the following **formula identities**. Changing behavior later requires a new formula version plus golden-fixture updates (handoff §34).

Runtime results expose `formula_id`, `formula_version`, `source_reference`, `assumptions`, `precision`, and explanation. Each module’s `source_reference` matches the Runtime string in its section below.

### Provenance checklist

| Field | Requirement |
|-------|-------------|
| Formula ID + version | Stable identity (e.g. `OG_ESTIMATE@v1`) |
| Exact algorithm / equation | One canonical definition per formula section |
| Constants | Listed once in that section’s Constants block (when applicable) |
| Units | Internal conversion targets |
| Assumptions | Explicit; no silent defaults for missing brewing losses |
| Rounding / precision | Per Global rounding policy and each section’s precision |
| Reference / source | Specific enough to re-derive the method; no duplicate citations |

Vague labels (e.g. “standard homebrew gravity points method,” “standard infusion equation,” “conventional brewing factors”) are forbidden in ADR text and runtime `source_reference`.

---

## Formula catalog (summary)

| Formula ID | Version | Section | Exact method (short) | Canonical reference |
|------------|---------|---------|----------------------|---------------------|
| `OG_ESTIMATE` | v1 | §A | Gravity points into batch volume | Palmer, *How to Brew*; Daniels, *Designing Great Beers* (PPG) |
| `FG_ESTIMATE` | v1 | §B | Attenuation applied to OG | Derived from §C |
| `APPARENT_ATTENUATION` | v1 | §C | SG form of AA% | SG rearrangement (not ASBC Plato) |
| `ABV` | v1 | §D | ABV from OG and FG | Palmer, *How to Brew* |
| `IBU` | v1 | §E | Tinseth utilization | Tinseth hop-utilization equations |
| `COLOR` | v1 | §F | Morey MCU→SRM | Morey SRM power-fit model |
| `WATER_REQUIREMENTS` | v1 | §G | Recorded mash/sparge (+ optional losses) | BrewingOS compositional definition |
| `STRIKE_TEMP` | v1 | §H | Palmer infusion strike | Palmer, *How to Brew*, infusion mash |
| `RECIPE_SCALING` | v1 | §I | Linear volume scale factor | BrewingOS proportional scaling |
| `UNIT_CONVERSION` | v1 | §J | Fixed conversion constants | NIST Handbook 44 / SI exact factors |

Each formula ID appears exactly once in this catalog.

---

## Principles

1. Results are **ESTIMATED** / **CALCULATED**, never **MEASURED**.
2. Missing required inputs → status `MISSING` (no fabricated authoritative value).
3. Invalid inputs → status `INVALID`.
4. Formula id + version are returned with every authoritative result.
5. Historical stored explanations must retain formula identity; future formula changes do not rewrite history.
6. Provenance must state the exact equation and constants used in code — not only a marketing name.

### Global rounding policy

Numeric results use `app.calculations.types.round_decimal` → `Decimal.quantize` at each section’s precision (Python `decimal` default: **ROUND_HALF_EVEN**), unless a section states otherwise.

---

## A. `OG_ESTIMATE` v1 — Gravity points method

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
- `potential_sg` is PPG-style SG (not Plato).
- Metric mass/volume inputs convert to lb / US gal via §J before this equation.
- Result kind is **ESTIMATED**.

### Rounding / precision

**3** decimal places (SG).

### References

1. John Palmer, *How to Brew* (Brewers Publications) — gravity / points for recipe formulation.
2. Ray Daniels, *Designing Great Beers* (Brewers Publications) — PPG formulation method.

### Runtime `source_reference`

`ADR-003 §A — OG = 1 + Σ(W_lb×(P−1)×1000×E/100) / (V_gal×1000); Palmer/Daniels PPG`

---

## B. `FG_ESTIMATE` v1 — Final gravity from expected apparent attenuation

### Units

OG, FG → **specific gravity**; attenuation \(A\) → **percent**.

### Equation

\[
\mathrm{FG} = 1 + (\mathrm{OG} - 1)\times\left(1 - \frac{A}{100}\right)
\]

### Assumptions

- Uses **expected** apparent attenuation (yeast profile / recipe line), not measured fermentation data.
- When OG is from `OG_ESTIMATE`, FG remains **ESTIMATED**.
- Algebraically consistent with §C.

### Rounding / precision

**3** decimal places (SG).

### References

Derived from §C. Yeast attenuation ranges are manufacturer data when supplied on the recipe line.

### Runtime `source_reference`

`ADR-003 §B — FG = 1+(OG−1)×(1−A/100); derived from apparent attenuation`

---

## C. `APPARENT_ATTENUATION` v1

### Units

OG, FG → **specific gravity**; result → **percent**.

### Equation

\[
\mathrm{AA\%} = \frac{\mathrm{OG} - \mathrm{FG}}{\mathrm{OG} - 1} \times 100
\]

### Assumptions

- SG-based form only (not ASBC Plato; that would be `APPARENT_ATTENUATION@v2`).
- Requires \(\mathrm{OG} > 1\); otherwise `INVALID`.

### Rounding / precision

**1** decimal place.

### References

1. Palmer, *How to Brew* — attenuation discussion (SG rearrangement used here).

### Runtime `source_reference`

`ADR-003 §C — AA% = ((OG−FG)/(OG−1))×100 (SG form; not ASBC Plato)`

---

## D. `ABV` v1

### Units

OG, FG → **specific gravity**; result → **% ABV**.

### Constant

| Symbol | Value | Meaning |
|--------|-------|---------|
| \(k_{\mathrm{ABV}}\) | `131.25` | Homebrew SG→%ABV factor |

### Equation

\[
\mathrm{ABV\%} = (\mathrm{OG} - \mathrm{FG}) \times k_{\mathrm{ABV}}
\]

### Assumptions

- Simplified homebrew approximation only (not Balling / high-gravity models; those would be `ABV@v2+`).
- Kind is **CALCULATED** when both gravities are supplied to this formula (upstream inputs may still be estimates).

### Rounding / precision

**2** decimal places.

### References

1. John Palmer, *How to Brew* (Brewers Publications) — homebrew ABV approximation using \(k_{\mathrm{ABV}}\).

### Runtime `source_reference`

`ADR-003 §D — ABV% = (OG−FG)×131.25; Palmer How to Brew approx.`

---

## E. `IBU` v1 — Tinseth

### Units (internal)

Hop mass → **grams**; wort volume → **liters**; alpha acid → **percent**; time → **minutes**; boil gravity → **SG**.

### Constants (Tinseth)

| Symbol | Value | Role |
|--------|-------|------|
| \(B\) | `1.65` | Bigness base |
| \(g\) | `0.000125` | Gravity-term base |
| \(k_t\) | `0.04` | Boil-time decay (per minute) |
| \(d\) | `4.15` | Boil-time divisor |

### Equations

\[
\mathrm{BF} = B \times g^{(G_b - 1)}
\]

\[
\mathrm{BTF} = \frac{1 - e^{-k_t\,t}}{d}
\]

\[
U = \mathrm{BF} \times \mathrm{BTF}
\]

\[
\mathrm{mg\,\alpha/L} = \frac{(\alpha/100)\times m_{\mathrm{hop}}^{\mathrm{(g)}} \times 1000}{V^{\mathrm{(L)}}}
\]

\[
\mathrm{IBU}_i = U \times (\mathrm{mg\,\alpha/L})_i,\quad
\mathrm{IBU} = \sum_i \mathrm{IBU}_i
\]

### Stage policy (v1)

| Stage | Contribution |
|-------|--------------|
| `BOIL`, `FIRST_WORT`, `WHIRLPOOL`, `MASH` | Tinseth with supplied `time_minutes` |
| `DRY_HOP` | **0 IBU** (explicit; not estimated) |

### Assumptions

- No pellet utilization multiplier in v1.
- Batch volume is the post-boil volume **proxy** for mg/L when a separate post-boil volume is unavailable (recorded on the result).
- Result kind is **ESTIMATED**.

### Rounding / precision

Total IBU → **1** decimal place.

### References

1. Glenn Tinseth — hop utilization / bitterness equations (Tinseth model); historically published via the Real Beer hop pages / Tinseth hop utilization write-up. Symbols \(B,g,k_t,d\) match the common software reproduction of that model.

### Runtime `source_reference`

`ADR-003 §E — Tinseth: U=1.65·0.000125^(Gb−1)·(1−e^(−0.04t))/4.15; dry-hop=0; no pellet factor`

---

## F. `COLOR` v1 — Morey SRM

### Units (internal)

Mass → **lb**; volume → **US gallon**; color → **°Lovibond**; result → **SRM**.

### Constants

| Symbol | Value | Role |
|--------|-------|------|
| \(a\) | `1.4922` | Morey scale |
| \(b\) | `0.6859` | Morey exponent |

### Equations

\[
\mathrm{MCU} = \sum_i \frac{W_i^{\mathrm{(lb)}} \times L_i}{V_{\mathrm{batch}}^{\mathrm{(gal)}}}
\]

\[
\mathrm{SRM} = a \times \mathrm{MCU}^{b}
\]

### Assumptions

- Color inputs are °Lovibond (or treated as such on recipe/ingredient snapshots).
- Morey power-fit only (not Mosher / Daniels color models).
- Result kind is **ESTIMATED**.

### Rounding / precision

**1** decimal place (SRM).

### References

1. Dan Morey — MCU→SRM power-fit model (constants \(a,b\) above), commonly cited in homebrew formulation references including Palmer, *How to Brew*.

### Runtime `source_reference`

`ADR-003 §F — Morey: SRM = 1.4922 × MCU^0.6859; MCU = Σ(W_lb×°L)/V_gal`

---

## G. `WATER_REQUIREMENTS` v1

### Units

Volumes in the caller’s unit after §J conversion when needed; totals in the requested output unit.

### Equations

\[
V_{\mathrm{total}} = V_{\mathrm{mash}} + V_{\mathrm{sparge}}
\]

\(V_{\mathrm{sparge}}\) is included only if recorded. Boil-off and trub are reported when recorded; otherwise **`NOT RECORDED`** (never defaulted).

Related helpers (same formula id family):

- Trub recorded: \(V_{\mathrm{post}} = V_{\mathrm{batch}} + V_{\mathrm{trub}}\); else \(V_{\mathrm{post}} \approx V_{\mathrm{batch}}\) (assumption noted on the result).
- Boil-off recorded: \(V_{\mathrm{pre}} = V_{\mathrm{post}} + V_{\mathrm{boil-off}}\); else pre-boil is `MISSING`.

### Assumptions

- No silent default boil-off rate, grain absorption, or trub loss.
- Sparge optional; mash water required for a total.
- No full water-chemistry / residual-alkalinity laboratory model in Epic 1.

### Rounding / precision

Volume totals → **3** decimal places in the output unit.

### References

BrewingOS ADR-003 compositional water accounting (Epic 1 scope).

### Runtime `source_reference`

`ADR-003 §G — V_total = V_mash + V_sparge(optional); losses NOT RECORDED if absent`

---

## H. `STRIKE_TEMP` v1 — Palmer infusion strike

### Units

Ratio \(r\) in **US quarts water per pound grain**. Temperatures computed in **°F**, then converted to **°C** for output.

### Constant

| Symbol | Value | Role |
|--------|-------|------|
| \(c\) | `0.2` | Grain thermal factor (qt/lb, °F) |

### Equation

\[
r = \frac{V_{\mathrm{water}}^{\mathrm{(qt)}}}{W_{\mathrm{grain}}^{\mathrm{(lb)}}}
\]

\[
T_w^{\mathrm{(°F)}} = \frac{c}{r}\,(T_{\mathrm{mash}}^{\mathrm{(°F)}} - T_{\mathrm{grain}}^{\mathrm{(°F)}}) + T_{\mathrm{mash}}^{\mathrm{(°F)}}
\]

### Assumptions

- Single-infusion mash only (no decoction / multi-infusion in v1).
- Grain and mash target temperatures are required (missing → `MISSING`; no implied room-temp default).

### Rounding / precision

Strike temperature → **1** decimal place (°C).

### References

1. John Palmer, *How to Brew* (Brewers Publications) — infusion mash strike-water temperature equation with factor \(c\) for qt/lb / °F.

### Runtime `source_reference`

`ADR-003 §H — Palmer: Tw°F = (0.2/r)(Tmash−Tgrain)+Tmash; r = qt water / lb grain`

---

## I. `RECIPE_SCALING` v1

### Units

Batch sizes → **US gallons** before the scale factor; ingredient amounts scaled in their native units.

### Equation

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

### Rounding / precision

Scale factor → **6** decimal places; scaled amounts → **4** decimal places.

### References

BrewingOS ADR-003 proportional scaling definition.

### Runtime `source_reference`

`ADR-003 §I — scale factor f = V_to_gal / V_from_gal; a′ = a×f (linear)`

---

## J. `UNIT_CONVERSION` v1

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

### Assumptions

- `gal` / `qt` are **US** liquid measures (not Imperial).
- Unsupported unit pairs → `INVALID` (no guessed factors).

### Rounding / precision

Converted results → **6** decimal places.

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
2. Any future equation or constant change requires a new formula version, updated golden fixtures, and PO approval.
3. Epic 1 treats §§A–J as the auditable calculation foundation.
