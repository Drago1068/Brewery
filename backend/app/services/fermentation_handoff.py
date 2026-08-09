"""Explicit fermentation handoff from CLOSED BrewSession (E2A-5).

Epic 2 boundary only — does not create FermentationSession or fermentation observations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import BrewPlan, BrewSession, FermentationHandoff
from app.domain.enums import BrewEventType, BrewSessionStatus
from app.schemas.brew_day import FermentationHandoffRequest
from app.services import brew_day_report as report_service
from app.services import brew_events as brew_events_service
from app.services import brew_session as brew_session_service
from app.services import idempotency as idempotency_service
from app.services import measurements as measurement_service

SCOPE_BREW_SESSION = "BREW_SESSION"
OPERATION = "CREATE_FERMENTATION_HANDOFF"

BOUNDARY_STATEMENT = {
    "epic_2_verified_or_recorded": [
        "Brew-Day process completion",
        "Brew-Day measurements",
        "Brew-Day deviations",
        "Brew-Day provenance",
        "Brew-Day audit state",
    ],
    "epic_3_must_verify_or_record": [
        "fermentation observations",
        "temperature targets over time",
        "gravity progression",
        "terminal-gravity evidence",
        "conditioning",
        "dry-hop/addition execution",
        "readiness-for-packaging handoff",
    ],
    "claims_fermentation_readiness": False,
}


def _illegal(code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": code, "message": message, **extra},
    )


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _measurement_context(requirements: list[dict], code: str) -> dict[str, Any]:
    """Honest planned vs actual context for a measurement code."""
    req = next((r for r in requirements if r["measurement_code"] == code), None)
    if req is None:
        return {
            "measurement_code": code,
            "requirement_present": False,
            "planned": None,
            "actual": {
                "status": "MISSING",
                "value": None,
                "unit": None,
                "kind": None,
                "note": "No Brew-Day measurement requirement for this code",
            },
        }
    record = req.get("record")
    planned = None
    if req.get("planned_value") is not None:
        planned = {
            "value": req["planned_value"],
            "unit": req["planned_unit"],
            "kind": req["planned_kind"],
        }
    status_val = req["status"]
    if status_val == "CAPTURED" and record is not None:
        actual = {
            "status": "CAPTURED",
            "value": record["display_value"],
            "unit": record["display_unit"],
            "kind": record["value_kind"],
            "confidence": record.get("confidence"),
            "measurement_record_id": record["id"],
            "raw_value": record.get("raw_value"),
            "corrected_value": record.get("corrected_value"),
        }
    elif status_val == "MISSED":
        actual = {
            "status": "MISSED",
            "value": None,
            "unit": None,
            "kind": None,
            "note": "OG: MISSING / MISSED" if code == "OG" else f"{code}: MISSING / MISSED",
        }
    elif status_val == "WAIVED":
        actual = {
            "status": "WAIVED",
            "value": None,
            "unit": None,
            "kind": None,
            "note": f"{code}: WAIVED — not recorded as measured",
        }
    else:
        actual = {
            "status": "PENDING_OR_UNRESOLVED",
            "value": None,
            "unit": None,
            "kind": None,
            "note": f"{code}: not recorded",
        }
    return {
        "measurement_code": code,
        "requirement_present": True,
        "requirement_id": req["id"],
        "requirement_level": req["requirement_level"],
        "requirement_status": status_val,
        "planned": planned,
        "actual": actual,
    }


def _yeast_context(plan: BrewPlan) -> dict[str, Any]:
    snap = plan.recipe_snapshot or {}
    ingredients = snap.get("ingredients") or snap.get("recipe_ingredients") or []
    yeast = [
        i
        for i in ingredients
        if isinstance(i, dict)
        and str(i.get("ingredient_type") or i.get("type") or "").upper() in ("YEAST",)
    ]
    return {
        "planned_yeast_ingredients": yeast,
        "note": "Planned yeast identity from BrewPlan recipe snapshot; not a fermentation observation",
    }


def handoff_to_dict(row: FermentationHandoff) -> dict:
    return {
        "id": row.id,
        "brewery_id": row.brewery_id,
        "brew_session_id": row.brew_session_id,
        "brew_plan_id": row.brew_plan_id,
        "recipe_version_id": row.recipe_version_id,
        "client_submission_id": row.client_submission_id,
        "created_by": row.created_by,
        "created_at": _iso(row.created_at),
        "brew_day_closed_at": _iso(row.brew_day_closed_at),
        "payload": row.payload,
    }


async def create_fermentation_handoff(
    db: AsyncSession, session_id: str, payload: FermentationHandoffRequest
) -> dict:
    actor_id = settings.default_actor_id
    fp = idempotency_service.fingerprint_payload(payload.model_dump(mode="json"))
    existing = await idempotency_service.lookup_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
    )
    replay = idempotency_service.resolve_idempotency_or_conflict(
        existing, operation_type=OPERATION, request_fingerprint=fp
    )
    if replay is not None:
        return replay

    session = await brew_session_service.get_brew_session(db, session_id)

    if payload.expected_session_version != session.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONCURRENCY_CONFLICT",
                "message": "expected_session_version does not match current BrewSession.version",
                "expected_session_version": payload.expected_session_version,
                "current_session_version": session.version,
            },
        )

    if session.status == BrewSessionStatus.ABORTED:
        raise _illegal(
            "SESSION_ABORTED_NO_HANDOFF",
            "ABORTED sessions cannot create a fermentation handoff",
            session_status=session.status,
        )
    if session.status == BrewSessionStatus.HANDED_OFF:
        raise _illegal(
            "FERMENTATION_HANDOFF_ALREADY_EXISTS",
            "BrewSession is already HANDED_OFF",
            session_status=session.status,
        )
    if session.status != BrewSessionStatus.CLOSED:
        raise _illegal(
            "SESSION_NOT_CLOSED_FOR_HANDOFF",
            "Fermentation handoff requires BrewSession.status == CLOSED",
            session_status=session.status,
        )

    existing_handoff = (
        await db.execute(
            select(FermentationHandoff).where(
                FermentationHandoff.brew_session_id == session_id
            )
        )
    ).scalar_one_or_none()
    if existing_handoff is not None:
        raise _illegal(
            "FERMENTATION_HANDOFF_ALREADY_EXISTS",
            "One BrewSession may create at most one Epic-2A fermentation handoff",
            handoff_id=existing_handoff.id,
        )

    plan = (
        await db.execute(select(BrewPlan).where(BrewPlan.id == session.brew_plan_id))
    ).scalar_one()
    requirements = await measurement_service.list_session_requirements(db, session_id)
    report = await report_service.build_brew_day_report(db, session_id)

    og = _measurement_context(requirements, "OG")
    knockout = _measurement_context(requirements, "KNOCKOUT_TEMP")
    pitch_temp = _measurement_context(requirements, "YEAST_PITCH_TEMP")
    # Prefer post-boil volume as transferred-to-fermenter context when known.
    transferred = _measurement_context(requirements, "POST_BOIL_VOLUME")

    now = datetime.now(timezone.utc)
    version_before = session.version

    handoff_payload = {
        "boundary": BOUNDARY_STATEMENT,
        "identities": {
            "brewery_id": session.brewery_id,
            "brew_session_id": session.id,
            "brew_plan_id": plan.id,
            "recipe_id": plan.recipe_id,
            "recipe_version_id": plan.recipe_version_id,
            "recipe_snapshot_identity": {
                "recipe_id": plan.recipe_id,
                "recipe_version_id": plan.recipe_version_id,
                "plan_created_at": _iso(plan.created_at),
            },
        },
        "batch_size_context": {
            "batch_size": str(plan.batch_size),
            "batch_size_unit": plan.batch_size_unit,
        },
        "measurements": {
            "og": og,
            "knockout_temp": knockout,
            "yeast_pitch_temp": pitch_temp,
            "transferred_volume": transferred,
        },
        "yeast_context": _yeast_context(plan),
        "brew_day_closed_at": _iso(session.closed_at),
        "handoff_created_at": _iso(now),
        "deviations": report.get("deviations_and_warnings", []),
        "completeness": report.get("data_completeness", {}),
        "process_adherence": {
            "stages_completed": report["process_adherence"]["stages_completed"],
            "stages_skipped": report["process_adherence"]["stages_skipped"],
            "skipped_stages": report["process_adherence"]["skipped_stages"],
        },
        "measurement_quality_refs": [
            {
                "measurement_code": q["measurement_code"],
                "requirement_id": q["requirement_id"],
                "confidence": q["confidence"],
                "latest_observation_history_id": q["history"]["latest_observation_history_id"],
            }
            for q in report.get("measurement_quality", [])
            if q["requirement_status"] == "CAPTURED"
        ],
        "does_not_include": [
            "FermentationSession",
            "fermentation observations",
            "terminal-gravity targets",
            "fermentation temperature targets",
        ],
    }

    handoff = FermentationHandoff(
        brewery_id=session.brewery_id,
        brew_session_id=session.id,
        brew_plan_id=plan.id,
        recipe_version_id=plan.recipe_version_id,
        client_submission_id=payload.client_submission_id,
        created_by=actor_id,
        created_at=now,
        brew_day_closed_at=session.closed_at,
        payload=handoff_payload,
    )
    db.add(handoff)
    await db.flush()

    session.status = BrewSessionStatus.HANDED_OFF

    await brew_events_service.append_brew_event(
        db,
        brewery_id=session.brewery_id,
        brew_plan_id=session.brew_plan_id,
        brew_session_id=session.id,
        event_type=BrewEventType.FERMENTATION_HANDOFF_CREATED,
        actor_id=actor_id,
        client_submission_id=payload.client_submission_id,
        payload={
            "fermentation_handoff_id": handoff.id,
            "brew_session_id": session.id,
            "from_status": BrewSessionStatus.CLOSED,
            "to_status": BrewSessionStatus.HANDED_OFF,
            "boundary_claims_fermentation_readiness": False,
        },
    )

    session.version = version_before + 1
    response = {
        "handoff": handoff_to_dict(handoff),
        "session_status": session.status,
        "session_version": session.version,
    }
    await idempotency_service.record_idempotency(
        db,
        scope_type=SCOPE_BREW_SESSION,
        scope_id=session_id,
        client_submission_id=payload.client_submission_id,
        operation_type=OPERATION,
        request_fingerprint=fp,
        resource_type="FermentationHandoff",
        resource_id=handoff.id,
        http_status=201,
        response_snapshot=response,
        actor_id=actor_id,
        session_version_before=version_before,
        session_version_after=session.version,
    )
    await db.commit()
    return {
        "handoff": handoff_to_dict(handoff),
        "session_status": session.status,
        "session_version": session.version,
    }


async def get_fermentation_handoff(db: AsyncSession, session_id: str) -> dict:
    await brew_session_service.get_brew_session(db, session_id)
    row = (
        await db.execute(
            select(FermentationHandoff).where(
                FermentationHandoff.brew_session_id == session_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="FermentationHandoff not found")
    return handoff_to_dict(row)
