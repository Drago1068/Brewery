# Brewing Domain Model

## Aggregate Roots

### Recipe
- Recipe
- RecipeVersion
- RecipeIngredient
- RecipeProcessStep
- WaterProfileTarget
- FermentationPlan
- PackagingPlan

### BrewSession
- BrewSession
- BrewStage
- BrewTimer
- Measurement
- Deviation
- BrewNote
- BrewJournalEvent

### Inventory
- Ingredient
- IngredientLot
- InventoryLocation
- InventoryTransaction
- InventoryReservation
- SafetyStockPolicy
- SupplierItem

### Equipment
- EquipmentProfile
- EquipmentItem
- CalibrationRecord
- MaintenanceRecord

### Fermentation
- FermentationSession
- FermentationMeasurement
- FermentationEvent

### Packaging
- PackagingSession
- PackageUnit
- Keg
- PackagedBeerLot
- PackageInventoryTransaction

### Serving
- Tap
- TapAssignment
- MenuItem
- MenuPublication

### Evaluation
- SensoryEvaluation
- SensoryDescriptor
- CompetitionEntry
- CompetitionFeedback

### Learning
- LearningModule
- Lesson
- Assessment
- LearningProgress
- PracticalExercise

## Recipe Lineage
Recipe → RecipeVersion → BrewSession → FermentationSession → PackagingSession → SensoryEvaluation → CompetitionEntry → RecipeVersion(next)

## Inventory Ledger
Stock on hand is derived from auditable inventory transactions:
PURCHASE, ADJUSTMENT, RESERVATION, RELEASE, CONSUMPTION, WASTE, TRANSFER, RETURN.

## Packaged Beer Ledger
Packaged inventory uses similarly auditable events:
FILLED, TRANSFERRED, TAPPED, SERVED_ESTIMATE, COUNT_ADJUSTMENT, EMPTIED, DISCARDED.

## Substitution
Substitutions are recommendations, never silent replacements. Each candidate contains:
- original ingredient
- substitute
- inventory availability
- conversion quantity
- expected flavor/process impact
- confidence
- brewer approval

## Measurements
Every measurement includes:
type, value, unit, measured_at, stage, target if applicable, instrument, confidence, note, and provenance.
