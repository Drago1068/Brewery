from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.domain.fermentation.models import (
    FermentationOgConsumption,
    FermentationPlanSnapshot,
    FermentationStageInstance,
    FermentationYeastPitchReference,
)
from brewing_api.domain.identity.models import User


def serialize_session(db: Session, user: User, fermentation_session_id: uuid.UUID) -> dict:
    session = get_fermentation_session(db, user, fermentation_session_id)
    stages = list(
        db.scalars(
            select(FermentationStageInstance)
            .where(FermentationStageInstance.fermentation_session_id == session.id)
            .order_by(FermentationStageInstance.created_at)
        ).all()
    )
    snapshot = db.scalar(
        select(FermentationPlanSnapshot).where(
            FermentationPlanSnapshot.fermentation_session_id == session.id
        )
    )
    og = db.scalar(
        select(FermentationOgConsumption).where(
            FermentationOgConsumption.fermentation_session_id == session.id
        )
    )
    yeast = db.scalar(
        select(FermentationYeastPitchReference).where(
            FermentationYeastPitchReference.fermentation_session_id == session.id
        )
    )
    return {
        "id": str(session.id),
        "brew_session_id": str(session.brew_session_id),
        "status": session.status,
        "revision": session.revision,
        "started_at": session.started_at,
        "plan_kind": session.plan_kind,
        "logical_plan_hash": session.logical_plan_hash,
        "plan_preview_hash": session.plan_preview_hash,
        "materialized_at": session.materialized_at,
        "expected_brew_revision": session.expected_brew_revision,
        "stages": [
            {
                "id": str(stage.id),
                "canonical_stage_type": stage.canonical_stage_type,
                "occurrence_number": stage.occurrence_number,
                "status": stage.status,
                "started_at": stage.started_at,
                "completed_at": stage.completed_at,
            }
            for stage in stages
        ],
        "plan_snapshot": None
        if snapshot is None
        else {
            "plan_kind": snapshot.plan_kind,
            "logical_plan_hash": snapshot.logical_plan_hash,
            "preview_hash": snapshot.preview_hash,
            "payload": snapshot.payload,
        },
        "og_consumption": None
        if og is None
        else {
            "brew_measurement_id": str(og.brew_measurement_id),
            "consumed_value": str(og.consumed_value),
            "consumed_unit": og.consumed_unit,
            "consumed_at": og.consumed_at,
            "schema_version": og.schema_version,
        },
        "yeast_pitch_reference": None
        if yeast is None
        else {
            "brew_pitch_handoff_id": str(yeast.brew_pitch_handoff_id),
            "yeast_note": yeast.yeast_note,
            "pitch_temperature_c": None
            if yeast.pitch_temperature_c is None
            else str(yeast.pitch_temperature_c),
            "pitched_at": yeast.pitched_at,
        },
    }
