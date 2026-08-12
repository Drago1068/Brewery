"""Imports all model modules for SQLAlchemy/Alembic metadata discovery."""

from brewing_api.domain.audit.models import AuditEvent, BrewJournalEvent
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.equipment.models import EquipmentProfile
from brewing_api.domain.identity.models import AuthSession, User
from brewing_api.domain.ingredients.models import Ingredient, IngredientLot, Supplier, SupplierItem
from brewing_api.domain.inventory.models import (
    InventoryLocation,
    InventoryReservation,
    InventoryTransaction,
    SafetyStockPolicy,
)
from brewing_api.domain.measurements.models import Deviation, Measurement
from brewing_api.domain.notifications.models import Notification
from brewing_api.domain.recipes.models import (
    IngredientSubstitution,
    Recipe,
    RecipeIngredient,
    RecipeProcessStep,
    RecipeVersion,
    WaterProfileTarget,
)

__all__ = [
    "AuditEvent",
    "AuthSession",
    "BrewJournalEvent",
    "BrewSession",
    "BrewStage",
    "BrewTimer",
    "Deviation",
    "EquipmentProfile",
    "Ingredient",
    "IngredientLot",
    "IngredientSubstitution",
    "InventoryLocation",
    "InventoryReservation",
    "InventoryTransaction",
    "Measurement",
    "Notification",
    "Recipe",
    "RecipeIngredient",
    "RecipeProcessStep",
    "RecipeVersion",
    "SafetyStockPolicy",
    "Supplier",
    "SupplierItem",
    "User",
    "WaterProfileTarget",
]
