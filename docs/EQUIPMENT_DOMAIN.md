# Equipment Domain

`EquipmentProfile` is owned by one user and supplies the process assumptions used by recipe calculations: default batch size, preferred display units, mash/brewhouse efficiency, boil-off, vessel/process losses, dead space, and absorption rates.

Recipes reference the source profile but also persist a complete calculation-relevant snapshot. Editing a live profile therefore cannot silently change historical targets. Detailed equipment components, calibration, and maintenance are future-compatible but deliberately outside Phase 2.

Validation requires positive batch size, efficiencies in `(0, 1]`, non-negative losses, and supported preference units. Every API lookup is ownership-scoped.
