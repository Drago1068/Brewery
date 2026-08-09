"""BrewPlan creation from immutable RecipeVersion baselines (E2A-1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import BrewPlan, EquipmentProfile
from app.domain import brew_day as brew_day_domain
from app.domain.enums import AuditAction, BrewEventType, BrewPlanStatus, ReadinessLevel
from app.schemas.brew_day import BrewPlanCreate, BrewPlanRead
from app.services import audit
from app.services import brew_events as brew_events_service
from app.services import calculation as calculation_service
from app.services import idempotency as idempotency_service
from app.services import readiness as readiness_service
from app.services.recipe import get_recipe, get_version

OPERATION_CREATE_BREW_PLAN = "CREATE_BREW_PLAN"
SCOPE_RECIPE_VERSION = "RECIPE_VERSION"


def _plan_to_read(plan: BrewPlan) -> BrewPlanRead:
    return BrewPlanRead(
        id=plan.id,
        brewery_id=plan.brewery_id,
        recipe_id=plan.recipe_id,
        recipe_version_id=plan.recipe_version_id,
        status=plan.status,
        batch_size=plan.batch_size,
        batch_size_unit=plan.batch_size_unit,
        brewhouse_efficiency=plan.brewhouse_efficiency,
        equipment_profile_id=plan.equipment_profile_id,
        equipment_snapshot=plan.equipment_snapshot,
        recipe_snapshot=plan.recipe_snapshot,
        planned_calculation_snapshot=plan.planned_calculation_snapshot,
        readiness_status=plan.readiness_status,
        readiness_summary=plan.readiness_summary,
        readiness_checks_snapshot=plan.readiness_checks_snapshot,
        readiness_acknowledged=plan.readiness_acknowledged,
        readiness_acknowledged_at=plan.readiness_acknowledged_at,
        readiness_acknowledged_by=plan.readiness_acknowledged_by,
        readiness_acknowledgement_note=plan.readiness_acknowledgement_note,
        created_by=plan.created_by,
        created_at=plan.created_at,
    )


def _fingerprint_body(payload: BrewPlanCreate) -> str:
    body: dict[str, Any] = {
        "readiness_acknowledgement": None,
    }
    if payload.readiness_acknowledgement is not None:
        ack = payload.readiness_acknowledgement
        body["readiness_acknowledgement"] = {
            "acknowledged": ack.acknowledged,
            "note": ack.note,
            "actor_id": ack.actor_id,
        }
    return idempotency_service.fingerprint_payload(body)


async def create_brew_plan(
    db: AsyncSession,
    recipe_version_id: str,
    payload: BrewPlanCreate,
) -> dict:
    """Create BrewPlan atomically with idempotency ledger + canonical BrewEvents.

    Writes PLAN_CREATED and (when applicable) READINESS_ACKNOWLEDGED to brew_events
    in the same transaction. Also retains append-only audit_events for continuity
    with E2A-1 evidence; brew_events is the brew-day domain stream.
    """
    fp = _fingerprint_body(payload)
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_RECIPE_VERSION,
        scope_id=recipe_version_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing,
        operation_type=OPERATION_CREATE_BREW_PLAN,
        request_fingerprint=fp,
    )
    if replay is not None:
        return replay

    version = await get_version(db, recipe_version_id)
    try:
        brew_day_domain.assert_planable_version_status(version.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "RECIPE_VERSION_NOT_PLANABLE", "message": str(exc)},
        ) from exc

    recipe = await get_recipe(db, version.recipe_id)
    actor = settings.default_actor_id

    readiness = await readiness_service.evaluate_recipe_version(db, recipe_version_id)
    overall = readiness["overall"]
    checks = readiness.get("checks") or []
    summary = readiness.get("summary") or ""

    acknowledged = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledgement_note: Optional[str] = None

    if overall in (ReadinessLevel.YELLOW, ReadinessLevel.RED, "YELLOW", "RED"):
        ack = payload.readiness_acknowledgement
        if ack is None or ack.acknowledged is not True:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "READINESS_ACKNOWLEDGEMENT_REQUIRED",
                    "message": (
                        f"Readiness is {overall}; explicit acknowledgement is required"
                    ),
                    "readiness_status": overall,
                    "readiness_summary": summary,
                    "checks": checks,
                },
            )
        acknowledged = True
        acknowledged_at = datetime.now(timezone.utc)
        acknowledged_by = ack.actor_id or actor
        acknowledgement_note = ack.note
    elif payload.readiness_acknowledgement is not None:
        # GREEN does not require acknowledgement; ignore spurious ack without converting status.
        # Still allow clients to send acknowledged=false/null-equivalent; reject if they claim ack.
        ack = payload.readiness_acknowledgement
        if ack.acknowledged is True:
            # Accept but do not pretend readiness changed; store only if they insist? Spec: GREEN
            # requires no acknowledgement. Reject extra acknowledgement to keep semantics clean.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "READINESS_ACKNOWLEDGEMENT_NOT_ALLOWED",
                    "message": "GREEN readiness does not accept acknowledgement",
                    "readiness_status": overall,
                },
            )

    equipment = None
    if version.equipment_profile_id:
        equipment = await db.get(EquipmentProfile, version.equipment_profile_id)

    calc_payload = await calculation_service.calculate_version(db, recipe_version_id)
    recipe_snapshot = brew_day_domain.build_recipe_snapshot(recipe, version)
    calc_snapshot = brew_day_domain.build_planned_calculation_snapshot(calc_payload)
    equipment_snapshot = brew_day_domain.build_equipment_snapshot(equipment)

    plan = BrewPlan(
        brewery_id=recipe.brewery_id,
        recipe_id=recipe.id,
        recipe_version_id=version.id,
        status=BrewPlanStatus.CREATED,
        batch_size=version.batch_size,
        batch_size_unit=version.batch_size_unit,
        brewhouse_efficiency=version.brewhouse_efficiency,
        equipment_profile_id=version.equipment_profile_id,
        equipment_snapshot=equipment_snapshot,
        recipe_snapshot=recipe_snapshot,
        planned_calculation_snapshot=calc_snapshot,
        readiness_status=overall,
        readiness_summary=summary,
        readiness_checks_snapshot=brew_day_domain.json_safe(checks),
        readiness_acknowledged=acknowledged,
        readiness_acknowledged_at=acknowledged_at,
        readiness_acknowledged_by=acknowledged_by,
        readiness_acknowledgement_note=acknowledgement_note,
        created_by=actor,
    )
    db.add(plan)
    await db.flush()
    await db.refresh(plan)

    await audit.record_audit(
        db,
        action=AuditAction.PLAN_CREATED,
        entity_type="BrewPlan",
        entity_id=plan.id,
        actor_id=actor,
        brewery_id=plan.brewery_id,
        summary=f"BrewPlan created from RecipeVersion {version.id}",
        details={
            "brew_plan_id": plan.id,
            "recipe_version_id": version.id,
            "readiness_status": overall,
            "recipe_version_status": version.status,
        },
    )
    await brew_events_service.append_brew_event(
        db,
        brewery_id=plan.brewery_id,
        brew_plan_id=plan.id,
        event_type=BrewEventType.PLAN_CREATED,
        actor_id=actor,
        payload={
            "brew_plan_id": plan.id,
            "recipe_version_id": version.id,
            "recipe_id": recipe.id,
            "readiness_status": overall,
        },
        client_submission_id=payload.client_submission_id,
        correlation_key=f"live:PLAN_CREATED:{plan.id}",
    )

    if acknowledged:
        # Distinct event from PLAN_CREATED (ADR-004).
        await audit.record_audit(
            db,
            action=AuditAction.READINESS_ACKNOWLEDGED,
            entity_type="BrewPlan",
            entity_id=plan.id,
            actor_id=acknowledged_by or actor,
            brewery_id=plan.brewery_id,
            summary=f"Readiness {overall} acknowledged for BrewPlan {plan.id}",
            details={
                "brew_plan_id": plan.id,
                "readiness_status": overall,
                "readiness_summary": summary,
                "checks": brew_day_domain.json_safe(checks),
                "note": acknowledgement_note,
                "acknowledged_at": acknowledged_at.isoformat() if acknowledged_at else None,
            },
        )
        await brew_events_service.append_brew_event(
            db,
            brewery_id=plan.brewery_id,
            brew_plan_id=plan.id,
            event_type=BrewEventType.READINESS_ACKNOWLEDGED,
            actor_id=acknowledged_by or actor,
            payload={
                "brew_plan_id": plan.id,
                "readiness_status": overall,
                "readiness_summary": summary,
                "checks": brew_day_domain.json_safe(checks),
                "note": acknowledgement_note,
            },
            client_submission_id=payload.client_submission_id,
            correlation_key=f"live:READINESS_ACKNOWLEDGED:{plan.id}",
            occurred_at=acknowledged_at,
        )

    response = _plan_to_read(plan).model_dump(mode="json")
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_RECIPE_VERSION,
        scope_id=recipe_version_id,
        client_submission_id=payload.client_submission_id,
        operation_type=OPERATION_CREATE_BREW_PLAN,
        request_fingerprint=fp,
        resource_type="BrewPlan",
        resource_id=plan.id,
        http_status=201,
        response_snapshot=response,
        actor_id=actor,
    )
    await db.commit()
    await db.refresh(plan)
    return _plan_to_read(plan).model_dump(mode="json")


async def get_brew_plan(db: AsyncSession, plan_id: str) -> BrewPlan:
    plan = await db.get(BrewPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BrewPlan not found")
    return plan
