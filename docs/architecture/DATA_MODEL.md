# Data Model Baseline

## Primary Tables
users
brewing_profiles
equipment_profiles
equipment_items
calibration_records
maintenance_records

ingredients
ingredient_lots
inventory_locations
inventory_transactions
inventory_reservations
safety_stock_policies
suppliers
supplier_items

recipes
recipe_versions
recipe_ingredients
recipe_process_steps
water_profile_targets
fermentation_plans
packaging_plans

brew_sessions
brew_stages
brew_timers
measurements
deviations
brew_notes
brew_journal_events

fermentation_sessions
fermentation_measurements
fermentation_events

packaging_sessions
package_units
kegs
packaged_beer_lots
package_inventory_transactions

taps
tap_assignments
menu_items
menu_publications

sensory_evaluations
sensory_descriptors
competition_entries
competition_feedback

learning_modules
lessons
assessments
learning_progress

ai_interactions
audit_events
notifications

## Data Rules
- UUID identifiers unless a documented ADR selects otherwise.
- UTC timestamps.
- Explicit units on physical measurements.
- Recipe versions immutable after use in a brew session.
- Completed brew measurements are not silently overwritten.
- Inventory and package stock are ledger-driven.
- Derived quantities are recomputable from source data wherever feasible.
