"""Brew-Day audit/report derived read model (E2A-5). Strictly read-only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrewEvent, BrewPlan, MeasurementObservationHistory
from app.domain.brew_day_report import compare_planned_actual
from app.domain.enums import (
    BrewEventType,
    BrewSessionStatus,
    BrewStageStatus,
    MeasurementObservationEventClass,
    MeasurementRequirementLevel,
    MeasurementRequirementStatus,
)
from app.services import brew_session as brew_session_service
from app.services import brew_timers as brew_timers_service
from app.services import measurements as measurement_service


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _count_by_status(items: list[dict], level: str) -> dict[str, int]:
    filtered = [r for r in items if r["requirement_level"] == level]
    statuses = {
        "total": len(filtered),
        "captured": 0,
        "missed": 0,
        "waived": 0,
        "pending": 0,
    }
    for req in filtered:
        key = req["status"].lower()
        if key in statuses:
            statuses[key] += 1
    return statuses


async def _observation_summary(
    db: AsyncSession, requirement_id: str
) -> dict[str, Any]:
    result = await db.execute(
        select(MeasurementObservationHistory)
        .where(MeasurementObservationHistory.requirement_id == requirement_id)
        .order_by(
            MeasurementObservationHistory.occurred_at.asc(),
            MeasurementObservationHistory.id.asc(),
        )
    )
    rows = result.scalars().all()
    classes = [r.event_class for r in rows]
    return {
        "observation_count": len(rows),
        "has_raw_capture": MeasurementObservationEventClass.RAW_CAPTURE in classes,
        "has_instrument_correction": (
            MeasurementObservationEventClass.INSTRUMENT_CORRECTION in classes
        ),
        "has_user_revision": MeasurementObservationEventClass.USER_REVISION in classes,
        "event_classes": classes,
        "latest_observation_history_id": rows[-1].id if rows else None,
        "first_observation_history_id": rows[0].id if rows else None,
        "original_raw_value": rows[0].raw_value if rows else None,
        "original_raw_unit": rows[0].raw_unit if rows else None,
    }


async def build_brew_day_report(db: AsyncSession, session_id: str) -> dict:
    """Derived read model. Zero persistence side effects."""
    session = await brew_session_service.get_brew_session(db, session_id)
    plan_result = await db.execute(select(BrewPlan).where(BrewPlan.id == session.brew_plan_id))
    plan = plan_result.scalar_one()

    requirements = await measurement_service.list_session_requirements(db, session_id)
    timers_payload = await brew_timers_service.list_session_timers(db, session_id)

    events = (
        await db.execute(
            select(BrewEvent)
            .where(BrewEvent.brew_session_id == session_id)
            .order_by(BrewEvent.occurred_at.asc(), BrewEvent.id.asc())
        )
    ).scalars().all()

    duration_seconds = None
    if session.started_at and session.closed_at:
        start = session.started_at
        end = session.closed_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        duration_seconds = int((end - start).total_seconds())

    recipe_snapshot = plan.recipe_snapshot or {}
    session_summary = {
        "brew_session_id": session.id,
        "brewery_id": session.brewery_id,
        "brew_plan_id": plan.id,
        "recipe_id": plan.recipe_id,
        "recipe_version_id": plan.recipe_version_id,
        "recipe_name": recipe_snapshot.get("name")
        or (recipe_snapshot.get("recipe") or {}).get("name"),
        "batch_size": str(plan.batch_size),
        "batch_size_unit": plan.batch_size_unit,
        "equipment_profile_id": plan.equipment_profile_id,
        "equipment_snapshot": plan.equipment_snapshot,
        "status": session.status,
        "current_stage_code": session.current_stage_code,
        "version": session.version,
        "started_at": _iso(session.started_at),
        "closed_at": _iso(session.closed_at),
        "abort_reason": session.abort_reason,
        "elapsed_brew_day_seconds": duration_seconds,
        "report_classification": (
            "ABORTED_INCOMPLETE"
            if session.status == BrewSessionStatus.ABORTED
            else (
                "HANDED_OFF"
                if session.status == BrewSessionStatus.HANDED_OFF
                else (
                    "CLOSED"
                    if session.status == BrewSessionStatus.CLOSED
                    else "IN_PROGRESS_OR_OPEN"
                )
            )
        ),
        "overall_brew_score": None,
    }

    completeness = {
        "required": _count_by_status(requirements, MeasurementRequirementLevel.REQUIRED),
        "recommended": _count_by_status(
            requirements, MeasurementRequirementLevel.RECOMMENDED
        ),
        "requirements": [
            {
                "id": r["id"],
                "measurement_code": r["measurement_code"],
                "requirement_level": r["requirement_level"],
                "status": r["status"],
                "stage_occurrence_id": r["stage_occurrence_id"],
            }
            for r in requirements
        ],
    }

    stages = sorted(session.stage_occurrences, key=lambda s: s.sequence_no)
    completed = [s for s in stages if s.status == BrewStageStatus.COMPLETED]
    skipped = [s for s in stages if s.status == BrewStageStatus.SKIPPED]
    pause_events = [e for e in events if e.event_type == BrewEventType.SESSION_PAUSED]
    resume_events = [e for e in events if e.event_type == BrewEventType.SESSION_RESUMED]
    process_adherence = {
        "stages_total": len(stages),
        "stages_completed": len(completed),
        "stages_skipped": len(skipped),
        "stages_pending": sum(1 for s in stages if s.status == BrewStageStatus.PENDING),
        "stages_active": sum(1 for s in stages if s.status == BrewStageStatus.ACTIVE),
        "skipped_stages": [
            {
                "stage_code": s.stage_code,
                "sequence_no": s.sequence_no,
                "skip_reason": s.skip_reason,
                "entered_at": _iso(s.entered_at),
                "exited_at": _iso(s.exited_at),
            }
            for s in skipped
        ],
        "stage_timeline": [
            {
                "stage_code": s.stage_code,
                "sequence_no": s.sequence_no,
                "status": s.status,
                "skip_reason": s.skip_reason,
                "entered_at": _iso(s.entered_at),
                "exited_at": _iso(s.exited_at),
            }
            for s in stages
        ],
        "pause_count": len(pause_events),
        "resume_count": len(resume_events),
        "aborted": session.status == BrewSessionStatus.ABORTED,
        "abort_reason": session.abort_reason,
    }

    planned_vs_actual: list[dict] = []
    measurement_quality: list[dict] = []
    for req in requirements:
        record = req.get("record")
        actual_value = record["display_value"] if record else None
        actual_unit = record["display_unit"] if record else None
        actual_kind = record["value_kind"] if record else None
        comparison = compare_planned_actual(
            planned_value=req.get("planned_value"),
            planned_unit=req.get("planned_unit"),
            planned_kind=req.get("planned_kind"),
            actual_value=actual_value,
            actual_unit=actual_unit,
            actual_kind=actual_kind,
            requirement_status=req["status"],
        )
        comparison["measurement_code"] = req["measurement_code"]
        comparison["requirement_id"] = req["id"]
        comparison["requirement_level"] = req["requirement_level"]
        planned_vs_actual.append(comparison)

        obs = await _observation_summary(db, req["id"])
        quality = {
            "requirement_id": req["id"],
            "measurement_code": req["measurement_code"],
            "requirement_status": req["status"],
            "confidence": record["confidence"] if record else None,
            "instrument": record["instrument"] if record else None,
            "method": record["method"] if record else None,
            "provenance": record["provenance"] if record else None,
            "validation_class": record["validation_class"] if record else None,
            "validation_notes": record["validation_notes"] if record else None,
            "correction_present": bool(record and record.get("corrected_value") is not None),
            "display_value": actual_value,
            "display_unit": actual_unit,
            "raw_value": record["raw_value"] if record else None,
            "raw_unit": record["raw_unit"] if record else None,
            "corrected_value": record["corrected_value"] if record else None,
            "corrected_unit": record["corrected_unit"] if record else None,
            "history": obs,
        }
        measurement_quality.append(quality)

    timer_evidence = []
    for t in timers_payload.get("timers", []):
        overrun = bool(
            t.get("elapsed_at")
            or t.get("computed_past_due")
            or t.get("status") == "ELAPSED"
        )
        timer_evidence.append(
            {
                "id": t["id"],
                "label": t["label"],
                "target_duration_seconds": t.get("target_duration_seconds"),
                "started_at": t.get("started_at"),
                "ends_at": t.get("ends_at"),
                "elapsed_at": t.get("elapsed_at"),
                "stopped_at": t.get("stopped_at"),
                "cancelled_at": t.get("cancelled_at"),
                "status": t.get("status"),
                "computed_past_due": t.get("computed_past_due"),
                "stage_occurrence_id": t.get("stage_occurrence_id"),
                "overrun_or_elapsed_evidence": overrun,
            }
        )

    deviations: list[dict] = []
    for s in skipped:
        deviations.append(
            {
                "type": "STAGE_SKIPPED",
                "stage_code": s.stage_code,
                "skip_reason": s.skip_reason,
            }
        )
    for req in requirements:
        if req["status"] == MeasurementRequirementStatus.MISSED:
            deviations.append(
                {
                    "type": "MEASUREMENT_MISSED",
                    "measurement_code": req["measurement_code"],
                    "requirement_level": req["requirement_level"],
                }
            )
        elif req["status"] == MeasurementRequirementStatus.WAIVED:
            deviations.append(
                {
                    "type": "MEASUREMENT_WAIVED",
                    "measurement_code": req["measurement_code"],
                    "requirement_level": req["requirement_level"],
                }
            )
        record = req.get("record")
        if record and record.get("validation_class") in (
            "UNUSUAL_VALUE",
            "DOMAIN_CONCERN",
            "INPUT_ERROR",
        ):
            deviations.append(
                {
                    "type": "VALIDATION_WARNING",
                    "measurement_code": req["measurement_code"],
                    "validation_class": record["validation_class"],
                    "validation_notes": record.get("validation_notes"),
                }
            )
    for t in timer_evidence:
        if t["overrun_or_elapsed_evidence"]:
            deviations.append(
                {
                    "type": "TIMER_OVERRUN_OR_ELAPSED",
                    "timer_id": t["id"],
                    "label": t["label"],
                    "status": t["status"],
                    "computed_past_due": t["computed_past_due"],
                }
            )
    if session.status == BrewSessionStatus.ABORTED:
        deviations.append(
            {
                "type": "SESSION_ABORTED",
                "abort_reason": session.abort_reason,
            }
        )

    readiness = {
        "readiness_status": plan.readiness_status,
        "readiness_summary": plan.readiness_summary,
        "readiness_checks_snapshot": plan.readiness_checks_snapshot,
        "readiness_acknowledged": plan.readiness_acknowledged,
        "readiness_acknowledged_at": _iso(plan.readiness_acknowledged_at),
        "readiness_acknowledged_by": plan.readiness_acknowledged_by,
        "readiness_acknowledgement_note": plan.readiness_acknowledgement_note,
        "reinterpreted_as_green": False,
    }
    if plan.readiness_status in ("YELLOW", "RED") and plan.readiness_acknowledged:
        deviations.append(
            {
                "type": "READINESS_ACKNOWLEDGED",
                "original_readiness_status": plan.readiness_status,
                "acknowledged_by": plan.readiness_acknowledged_by,
                "acknowledged_at": _iso(plan.readiness_acknowledged_at),
                "note": plan.readiness_acknowledgement_note,
            }
        )

    return {
        "brew_session_id": session_id,
        "generated_at": _iso(datetime.now(timezone.utc)),
        "session_summary": session_summary,
        "data_completeness": completeness,
        "process_adherence": process_adherence,
        "planned_vs_actual": planned_vs_actual,
        "measurement_quality": measurement_quality,
        "timer_evidence": timer_evidence,
        "deviations_and_warnings": deviations,
        "readiness_acknowledgement": readiness,
        "overall_brew_score": None,
        "dimensions_are_independent": True,
        "event_count": len(events),
    }


async def get_brew_day_report(db: AsyncSession, session_id: str) -> dict:
    await brew_session_service.get_brew_session(db, session_id)
    return await build_brew_day_report(db, session_id)
