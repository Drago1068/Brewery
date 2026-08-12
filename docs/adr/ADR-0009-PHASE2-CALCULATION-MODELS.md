# ADR-0009 — Phase 2 Calculation Models

Status: Accepted for Phase 2

## Decision

The initial authoritative models are:

- extract/OG: gravity points from fermentable potential points per pound per gallon, adjusted by brewhouse efficiency and converted from canonical units
- expected FG: `1 + (OG - 1) × (1 - apparent attenuation)`
- ABV: `(OG - FG) × 131.25`
- bitterness: Tinseth utilization model
- color: Morey equation from Malt Color Units
- strike temperature: standard infusion equation using a configurable grain thermal ratio constant of `0.2`
- pitch requirement: ale/lager cells-per-milliliter-per-degree-Plato foundation
- priming sugar: deterministic glucose-equivalent estimate from target/residual CO₂ and packaged volume

Model identifiers and assumptions are included in every saved calculation snapshot. Alternative models require explicit future selection; models are never silently mixed.

## Boundary

These are planning estimates, not guaranteed biological or equipment outcomes. Advanced acid/base equilibrium, yeast viability, detailed equipment-specific hop utilization, and statistical prediction remain deferred.
