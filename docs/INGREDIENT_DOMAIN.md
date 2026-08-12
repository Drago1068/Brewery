# Ingredient Domain

The catalog supports `FERMENTABLE`, `HOP`, `YEAST`, `WATER_ADDITION`, `ADJUNCT`, `FINING`, `NUTRIENT`, and `MISCELLANEOUS`. Common identity and canonical unit fields are relational; optional category metadata lives in an extensible JSON attribute document.

Fermentables require potential PPG for authoritative extract calculations. Hops require a catalog alpha-acid default. A hop lot may override that value, and recipe calculation prefers the selected lot value. Yeast, salt/acid, descriptive, manufacturer, and optional performance ranges can expand without schema redesign; marketing data is not treated as guaranteed performance.

Lots preserve supplier, dates, received quantity, cost, expiry, optional hop alpha acid, optional yeast dates, and notes. Receipt appends a purchase transaction rather than creating mutable stock.
