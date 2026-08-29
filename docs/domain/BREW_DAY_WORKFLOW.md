# Brew-Day Workflow

## State Model
PLANNED → READY → ACTIVE → PAUSED(optional) → COMPLETED
Exceptional state: ABORTED

## Initial Stages
1. Pre-Brew
2. Water Preparation
3. Milling
4. Mash-In
5. Mash
6. Lauter/Sparge
7. Pre-Boil
8. Boil
9. Whirlpool/Flameout
10. Chill
11. Transfer
12. Yeast Pitch
13. Brew Complete

## Stage Definition
Each stage may define:
- required inputs
- target values
- tolerance
- instructions
- timer
- triggered reminders
- ingredient additions
- required measurements
- optional measurements
- completion rule

## Mandatory Vertical-Slice Behavior
During Mash:
1. Start mash stage.
2. Persist mash start time.
3. Start persisted timer.
4. Trigger pH reminder according to workflow rule.
5. Capture pH with unit/provenance metadata.
6. Trigger mash-gravity request near completion.
7. Capture gravity.
8. Compare actuals with targets/tolerance.
9. Record any deviation.
10. Complete stage.
11. Create automatic journal entries.

Phase 3 extends this Mash slice across the canonical brew-day stages through yeast-pitch handoff. PostgreSQL remains authoritative for stage, timer, reminder, measurement, addition, waiver, and journal truth. Browser refresh reconstructs the current worksheet from `GET /api/v1/brew-sessions/{id}`. Phase 4 fermentation management is out of scope.
