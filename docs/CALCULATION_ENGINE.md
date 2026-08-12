# Deterministic Calculation Engine

`packages/calculations` is the authoritative Decimal-based engine. The API persists inputs, outputs, equipment assumptions, and model IDs on each recipe version; the browser only displays results.

Implemented Phase 2 models:

- extract from potential PPG, mass, batch volume, and brewhouse efficiency; OG from summed gravity points;
- FG estimate from OG and apparent attenuation; ABV `(OG - FG) × 131.25`;
- observed/potential efficiency ratio, with mash and brewhouse concepts kept distinct;
- Tinseth v1 bitterness and Morey v1 color;
- strike, sparge, total liquor, pre-boil, and post-boil volumes from batch target and snapshotted losses;
- strike temperature using the standard infusion heat-capacity approximation;
- practical ale pitch foundation at a configurable million-cells/ml/°P rate;
- residual-CO2 and glucose-equivalent priming sugar foundation;
- ion ppm from mineral mass fraction and water volume.

Scaling is process-aware: volume is the base factor; fermentables additionally compensate for source/target efficiency; salts follow total liquor; hops and yeast use volume foundations. Equipment losses are recalculated rather than blindly multiplied. These are planning estimates, not guaranteed biological outcomes.

Golden tests use externally meaningful conversion, OG/FG/ABV, Tinseth, Morey, water, pitch, carbonation, mineral, and scaling cases with explicit tolerances.
