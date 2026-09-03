from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.phase4.derived_gravity import latest_derived_gravity
from brewing_api.application.phase4.completion import current_fermentation_assessment, serialize_assessment
from brewing_api.application.phase4.conditioning import current_conditioning_assessment
from brewing_api.application.phase4.measurements import serialize_measurement
from brewing_api.application.phase4.pitch_rate import compute_pitch_rate_estimate
from brewing_api.application.phase4.reminders import project_reminders, serialize_reminder
from brewing_api.application.phase4.sessions import get_fermentation_session
from brewing_api.application.phase4.timers import project_timers, serialize_timer
from brewing_api.domain.fermentation.models import (
    FermentationMeasurement,
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
    measurements = list(
        db.scalars(
            select(FermentationMeasurement)
            .where(FermentationMeasurement.fermentation_session_id == session.id)
            .order_by(FermentationMeasurement.observed_at, FermentationMeasurement.created_at)
        ).all()
    )
    derived = latest_derived_gravity(db, session.id)
    assessment = current_fermentation_assessment(db, session.id)
    conditioning_assessment = current_conditioning_assessment(db, session.id)
    timers = project_timers(db, session.id)
    reminders = project_reminders(db, session.id)
    db.commit()
    pitch_rate_estimate = compute_pitch_rate_estimate(db, session, snapshot=snapshot, og=og)
    return {
        "id": str(session.id),
        "brew_session_id": str(session.brew_session_id),
        "status": session.status,
        "revision": session.revision,
        "started_at": session.started_at,
        "paused_at": session.paused_at,
        "pause_origin_state": session.pause_origin_state,
        "resumed_at": session.resumed_at,
        "fermentation_first_completed_at": session.fermentation_first_completed_at,
        "fermentation_current_completed_at": session.fermentation_current_completed_at,
        "conditioning_first_started_at": session.conditioning_first_started_at,
        "conditioning_started_at": session.conditioning_started_at,
        "conditioning_current_activation_started_at": session.conditioning_current_activation_started_at,
        "conditioning_first_completed_at": session.conditioning_first_completed_at,
        "conditioning_current_completed_at": session.conditioning_current_completed_at,
        "conditioning_completed_at": session.conditioning_completed_at,
        "conditioning_mode": session.conditioning_mode,
        "conditioning_skipped": session.conditioning_skipped,
        "aborted_at": session.aborted_at,
        "abort_reason": session.abort_reason,
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
                "activation_ordinal": stage.activation_ordinal,
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
        "measurements": [serialize_measurement(db, item) for item in measurements],
        "derived_gravity": None
        if derived is None
        else {
            "stable_gravity_status": derived.stable_gravity_status,
            "final_gravity_sg": None
            if derived.final_gravity_sg is None
            else str(derived.final_gravity_sg),
            "apparent_attenuation_ratio": None
            if derived.apparent_attenuation_ratio is None
            else str(derived.apparent_attenuation_ratio),
            "spread": None if derived.spread is None else str(derived.spread),
            "window_measurement_ids": derived.window_measurement_ids,
            "source_measurement_ids": derived.source_measurement_ids,
            "evaluated_at": derived.evaluated_at,
            "calculation_version": derived.calculation_version,
            "schema_version": derived.schema_version,
        },
        "pitch_rate_estimate": pitch_rate_estimate,
        "completion_assessment": None if assessment is None else serialize_assessment(assessment),
        "conditioning_assessment": None
        if conditioning_assessment is None
        else serialize_assessment(conditioning_assessment),
        "timers": [serialize_timer(timer) for timer in timers],
        "reminders": [serialize_reminder(reminder) for reminder in reminders],
    }
