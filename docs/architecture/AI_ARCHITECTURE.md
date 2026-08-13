# AI Architecture

The system separates the authoritative Brewing Data Core, deterministic calculation and rule services, and the bounded AI Orchestration Layer. AI consumes authorized data and deterministic outputs; it does not replace either foundation.

## AI Roles
Brewer Tutor
Recipe Engineer
Brew-Day Assistant
Troubleshooter
Sensory Analyst
Competition Coach
Process Analyst
Research Assistant
Creative Branding Assistant

## Tooling Pattern
AI reads authoritative platform context through bounded application tools and receives deterministic calculation outputs.

## Response Classification
AI-generated guidance should distinguish:
FACT
CALCULATION
OBSERVATION
INFERENCE
RECOMMENDATION
UNCERTAINTY

## Guardrails
- No silent recipe mutation.
- No silent ingredient substitution.
- No inventory mutation without an application command.
- No historical measurement overwrite.
- No fabricated sensory or competition evidence.
- Scientific uncertainty must be expressed when material.
- Recommendations must expose evidence, assumptions, confidence, and uncertainty.
- Voice-assisted data entry requires user confirmation and deterministic validation before persistence.
- No autonomous brewery-equipment control.

## Authority Boundary

> AI recommends and reasons. Deterministic software calculates, validates, records, and enforces rules.

AI may tutor, explain, diagnose, synthesize history, simulate options, draft creative assets, and recommend actions. Application services remain responsible for authorization, calculations, validation, inventory effects, workflow transitions, audit records, and immutable lineage.

## Future Intelligence

The Brewer Knowledge Engine, personal brewing profile, recipe-performance correlations, experiment synthesis, substitution compatibility, AI-assisted judging, judge-disagreement analysis, competition recommendations, and future-batch guidance are mandatory later-horizon capabilities. They require trusted historical evidence and evaluation before activation and remain advisory.

## Creative Branding
Beer names, tasting descriptions, and logo prompts/assets may be generated from brewer-provided inputs. They are creative content and do not alter recipe or batch facts.
