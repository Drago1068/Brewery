from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.enums import EquipmentSystemType, MASH_RELEVANT_TYPES, PreferredUnits, VolumeUnit
from app.schemas.brewery import BreweryCreate, EquipmentCreate


def test_brewery_create_valid_us():
    payload = BreweryCreate(
        name="  Nazario Home  ",
        preferred_units=PreferredUnits.US,
        timezone="America/New_York",
        default_batch_size=Decimal("5"),
        default_batch_size_unit=VolumeUnit.GAL,
        default_brewhouse_efficiency=Decimal("72"),
    )
    assert payload.name == "Nazario Home"


def test_brewery_rejects_metric_unit_with_us_preference():
    with pytest.raises(ValidationError):
        BreweryCreate(
            name="Test",
            preferred_units=PreferredUnits.US,
            timezone="UTC",
            default_batch_size=Decimal("19"),
            default_batch_size_unit=VolumeUnit.L,
            default_brewhouse_efficiency=Decimal("70"),
        )


def test_brewery_rejects_zero_batch_and_bad_efficiency():
    with pytest.raises(ValidationError):
        BreweryCreate(
            name="Test",
            preferred_units=PreferredUnits.US,
            timezone="UTC",
            default_batch_size=Decimal("0"),
            default_batch_size_unit=VolumeUnit.GAL,
            default_brewhouse_efficiency=Decimal("70"),
        )
    with pytest.raises(ValidationError):
        BreweryCreate(
            name="Test",
            preferred_units=PreferredUnits.US,
            timezone="UTC",
            default_batch_size=Decimal("5"),
            default_batch_size_unit=VolumeUnit.GAL,
            default_brewhouse_efficiency=Decimal("0"),
        )


def test_extract_equipment_does_not_require_mash():
    payload = EquipmentCreate(
        name="Extract Kit Kettle",
        system_type=EquipmentSystemType.EXTRACT,
        target_batch_size=Decimal("5"),
        target_batch_size_unit=VolumeUnit.GAL,
        kettle_capacity=Decimal("8"),
        kettle_capacity_unit=VolumeUnit.GAL,
    )
    assert payload.mash_capacity is None
    assert EquipmentSystemType.EXTRACT not in MASH_RELEVANT_TYPES


def test_equipment_requires_unit_when_loss_set():
    with pytest.raises(ValidationError):
        EquipmentCreate(
            name="BIAB",
            system_type=EquipmentSystemType.BIAB,
            target_batch_size=Decimal("5"),
            target_batch_size_unit=VolumeUnit.GAL,
            kettle_capacity=Decimal("10"),
            kettle_capacity_unit=VolumeUnit.GAL,
            trub_loss=Decimal("0.5"),
        )


def test_biab_equipment_with_advanced_fields():
    payload = EquipmentCreate(
        name="Anvil Foundry",
        system_type=EquipmentSystemType.ELECTRIC_ALL_IN_ONE,
        target_batch_size=Decimal("5"),
        target_batch_size_unit=VolumeUnit.GAL,
        kettle_capacity=Decimal("10.5"),
        kettle_capacity_unit=VolumeUnit.GAL,
        mash_capacity=Decimal("10.5"),
        mash_capacity_unit=VolumeUnit.GAL,
        boil_off_rate=Decimal("0.75"),
        boil_off_rate_unit="gal/hr",
        trub_loss=Decimal("0.25"),
        trub_loss_unit=VolumeUnit.GAL,
        fermenter_loss=Decimal("0.25"),
        fermenter_loss_unit=VolumeUnit.GAL,
        typical_brewhouse_efficiency=Decimal("68"),
    )
    assert payload.system_type == EquipmentSystemType.ELECTRIC_ALL_IN_ONE
