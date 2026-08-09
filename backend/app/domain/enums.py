"""Shared domain enums for Epic 1."""

from enum import StrEnum


class PreferredUnits(StrEnum):
    US = "US"
    METRIC = "METRIC"


class VolumeUnit(StrEnum):
    GAL = "gal"
    L = "L"


class EquipmentSystemType(StrEnum):
    BIAB = "BIAB"
    ELECTRIC_ALL_IN_ONE = "ELECTRIC_ALL_IN_ONE"
    COOLER_MASH_TUN = "COOLER_MASH_TUN"
    TRADITIONAL_3_VESSEL = "TRADITIONAL_3_VESSEL"
    EXTRACT = "EXTRACT"
    PARTIAL_MASH = "PARTIAL_MASH"
    CUSTOM = "CUSTOM"


class AuditAction(StrEnum):
    BREWERY_CREATED = "BREWERY_CREATED"
    BREWERY_UPDATED = "BREWERY_UPDATED"
    EQUIPMENT_CREATED = "EQUIPMENT_CREATED"
    EQUIPMENT_UPDATED = "EQUIPMENT_UPDATED"
    INVENTORY_RECEIPT = "INVENTORY_RECEIPT"
    INVENTORY_ADJUSTMENT = "INVENTORY_ADJUSTMENT"
    INVENTORY_CONSUMPTION = "INVENTORY_CONSUMPTION"
    INVENTORY_WASTE = "INVENTORY_WASTE"
    INVENTORY_RESERVATION = "INVENTORY_RESERVATION"
    INVENTORY_RESERVATION_RELEASE = "INVENTORY_RESERVATION_RELEASE"
    RECIPE_CREATED = "RECIPE_CREATED"
    RECIPE_VERSION_CREATED = "RECIPE_VERSION_CREATED"
    RECIPE_VERSION_UPDATED = "RECIPE_VERSION_UPDATED"
    RECIPE_VERSION_ACTIVATED = "RECIPE_VERSION_ACTIVATED"
    RECIPE_VERSION_LOCKED = "RECIPE_VERSION_LOCKED"
    RECIPE_CLONED = "RECIPE_CLONED"


class RecipeStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class RecipeVersionStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    LOCKED = "LOCKED"


class HopStage(StrEnum):
    MASH = "MASH"
    FIRST_WORT = "FIRST_WORT"
    BOIL = "BOIL"
    WHIRLPOOL = "WHIRLPOOL"
    DRY_HOP = "DRY_HOP"


class MashMethod(StrEnum):
    SINGLE_INFUSION = "SINGLE_INFUSION"
    BIAB = "BIAB"
    STEP = "STEP"
    DECOCTION = "DECOCTION"
    OTHER = "OTHER"


EDITABLE_VERSION_STATUSES = frozenset({RecipeVersionStatus.DRAFT})
IMMUTABLE_VERSION_STATUSES = frozenset(
    {RecipeVersionStatus.ACTIVE, RecipeVersionStatus.SUPERSEDED, RecipeVersionStatus.LOCKED}
)


class IngredientCategory(StrEnum):
    FERMENTABLE = "FERMENTABLE"
    HOP = "HOP"
    YEAST = "YEAST"
    ADJUNCT = "ADJUNCT"
    WATER_ADDITION = "WATER_ADDITION"
    FINING = "FINING"
    OTHER = "OTHER"


class InventoryTransactionType(StrEnum):
    RECEIPT = "RECEIPT"
    CONSUMPTION = "CONSUMPTION"
    ADJUSTMENT = "ADJUSTMENT"
    WASTE = "WASTE"
    RESERVATION = "RESERVATION"
    RESERVATION_RELEASE = "RESERVATION_RELEASE"


class QuantityUnit(StrEnum):
    LB = "lb"
    OZ = "oz"
    KG = "kg"
    G = "g"
    GAL = "gal"
    L = "L"
    ML = "ml"
    EACH = "each"
    PACK = "pack"


class FermentableType(StrEnum):
    BASE_MALT = "BASE_MALT"
    SPECIALTY_MALT = "SPECIALTY_MALT"
    EXTRACT = "EXTRACT"
    SUGAR = "SUGAR"
    ADJUNCT_GRAIN = "ADJUNCT_GRAIN"
    OTHER = "OTHER"


class HopType(StrEnum):
    PELLET = "PELLET"
    WHOLE = "WHOLE"
    CRYO = "CRYO"
    EXTRACT = "EXTRACT"
    OTHER = "OTHER"


class YeastType(StrEnum):
    ALE = "ALE"
    LAGER = "LAGER"
    WHEAT = "WHEAT"
    WILD = "WILD"
    BACTERIA = "BACTERIA"
    OTHER = "OTHER"


class ReadinessLevel(StrEnum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class ReadinessSeverity(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKER = "BLOCKER"


# System types that typically require mash capacity / mash fields.
MASH_RELEVANT_TYPES = frozenset(
    {
        EquipmentSystemType.BIAB,
        EquipmentSystemType.ELECTRIC_ALL_IN_ONE,
        EquipmentSystemType.COOLER_MASH_TUN,
        EquipmentSystemType.TRADITIONAL_3_VESSEL,
        EquipmentSystemType.PARTIAL_MASH,
        EquipmentSystemType.CUSTOM,
    }
)
