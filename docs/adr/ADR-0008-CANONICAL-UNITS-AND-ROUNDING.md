# ADR-0008 — Canonical Units and Rounding

Status: Accepted for Phase 2

## Decision

Authoritative calculations use `Decimal` and canonical units:

- mass: grams (`g`)
- volume: liters (`L`)
- temperature: degrees Celsius (`degC`)
- gravity: specific gravity (`SG`)
- color: Standard Reference Method (`SRM`)
- concentration: parts per million (`ppm`)
- count: each (`each`)
- time: minutes unless the field explicitly declares seconds

Ingredient inventory and recipe lines store quantities in the ingredient's declared canonical unit. Boundary conversion is explicit and deterministic. Intermediate calculation values are not rounded. Persistence uses schema-declared decimal precision. UI formatting is presentation-only and never feeds a rounded value back into an authoritative calculation without an explicit command.

## Consequences

Mixed-unit arithmetic is rejected. Display preferences may use US customary units, but API payloads and stored calculation snapshots retain explicit canonical units. Formula-specific quantization occurs only at output/persistence boundaries and is documented by the calculation engine.
