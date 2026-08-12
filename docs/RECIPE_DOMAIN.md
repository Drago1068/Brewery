# Recipe Domain

`Recipe` is the conceptual beer. `RecipeVersion` is a complete formulation and calculation snapshot. Phase 2 adds style/BJCP metadata, batch/equipment assumptions, calculated targets, formulation lines, process-plan foundations, water targets, notes, and model identifiers.

Ingredient lines hold ingredient, optional lot, canonical amount/unit, use stage, optional timing/percentage, and notes. Supported hop-use foundations include mash, first wort, boil, whirlpool, and dry hop.

Creating a formulation saves version 1. Scaling/cloning always inserts the next version and copies/scales ingredient lines; it never overwrites the source. The accepted PostgreSQL trigger still blocks update/delete of any version already used by a brew session. Current availability is evaluated separately so historical calculations remain unchanged.

Manual substitution relationships specify ratio, process/flavor impact, confidence, and mandatory brewer approval. The system reports candidates but never replaces an ingredient automatically.
