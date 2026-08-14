import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from calculations import compare_measurement, planned_versus_actual
from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit, journal
from brewing_api.application.phase3.identities_compat import first_mash_stage, is_legacy_plan
from brewing_api.application.phase3.operations import replay_or_conflict, store_success
from brewing_api.application.phase3.plan import build_plan, persist_plan
from brewing_api.application.recipes import get_owned_version
from brewing_api.domain.audit.models import BrewJournalEvent
from brewing_api.domain.brew_day.identities import legacy_stage_instance_id
from brewing_api.domain.brew_day.models import (
    BrewAdditionEvent,
    BrewAttachment,
    BrewNote,
    BrewPlanStep,
    BrewReminderHistory,
    BrewStageRequirement,
    BrewWaiver,
)
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.identity.models import User
from brewing_api.domain.measurements.models import Deviation, Measurement
from brewing_api.domain.notifications.models import Notification
from brewing_api.domain.recipes.models import RecipeVersion
from brewing_api.platform.time import utc_now


class MeasurementCommand(Protocol):
    measurement_type: str
    value: Decimal
    unit: str
    measured_at: datetime | None
    note: str | None
    instrument: str | None
    entry_method: str
    operation_id: str | None
    late_entry_reason: str | None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _bump(session: BrewSession) -> None:
    session.revision = (session.revision or 1) + 1


def start_session(
    db: Session,
    user: User,
    version_id: uuid.UUID,
    declarations=(),
    preview_hash: str | None = None,
) -> BrewSession:
    version = get_owned_version(db, user, version_id)
    session = BrewSession(
        user_id=user.id,
        recipe_version_id=version.id,
        status="PLANNED",
        target_mash_temperature=version.target_mash_temperature,
        mash_temperature_unit=version.mash_temperature_unit,
        target_mash_ph=version.target_mash_ph,
        mash_ph_tolerance=version.mash_ph_tolerance,
        target_mash_gravity=version.target_mash_gravity,
        mash_gravity_tolerance=version.mash_gravity_tolerance,
        planned_mash_duration_minutes=version.planned_mash_duration_minutes,
    )
    db.add(session)
    db.flush()
    persist_plan(db, session, build_plan(db, version, declarations, preview_hash))
    audit(db, user.id, "BREW_SESSION_PLANNED", "BrewSession", session.id)
    db.commit()
    db.refresh(session)
    return session


def mark_ready(db: Session, user: User, session_id: uuid.UUID) -> BrewSession:
    session = get_session(db, user, session_id)
    if session.status != "PLANNED":
        raise ConflictError("Only a planned brew session can enter READY")
    if not session.logical_plan_hash:
        raise DomainError("Preflight failed: execution plan was not materialized", 422)
    session.status = "READY"
    journal(db, session.id, "BREW_SESSION_READY", "Brew session preflight passed", actor_id=user.id)
    audit(db, user.id, "BREW_SESSION_READY", "BrewSession", session.id)
    _bump(session)
    db.commit()
    db.refresh(session)
    return session


def activate_session(db: Session, user: User, session_id: uuid.UUID) -> BrewSession:
    session = get_session(db, user, session_id)
    if session.status == "PLANNED":
        session = mark_ready(db, user, session_id)
    if session.status != "READY":
        raise ConflictError("Only a ready brew session can be started")
    active = db.scalar(
        select(BrewSession).where(
            BrewSession.user_id == user.id,
            BrewSession.status.in_(("ACTIVE", "PAUSED")),
            BrewSession.id != session.id,
        )
    )
    if active:
        raise ConflictError("An active brew session already exists")
    session.status = "ACTIVE"
    session.started_at = utc_now()
    _bump(session)
    journal(db, session.id, "BREW_SESSION_STARTED", "Brew session started", actor_id=user.id)
    audit(db, user.id, "BREW_SESSION_STARTED", "BrewSession", session.id)
    db.commit()
    db.refresh(session)
    return session


def complete_session(db: Session, user: User, session_id: uuid.UUID) -> BrewSession:
    session = get_session(db, user, session_id)
    if session.status != "ACTIVE":
        raise ConflictError("Only an active brew session can be completed")
    stages = list(
        db.scalars(select(BrewStage).where(BrewStage.brew_session_id == session.id)).all()
    )
    for stage in stages:
        if stage.required and stage.status not in {"COMPLETED", "SKIPPED"}:
            raise DomainError(f"Required stage incomplete: {stage.name}")
        if not stage.required and stage.status not in {"COMPLETED", "SKIPPED", "PENDING"}:
            raise DomainError(f"Optional stage unresolved: {stage.name}")
    now = utc_now()
    session.status = "COMPLETED"
    session.completed_at = now
    journal(db, session.id, "BREW_SESSION_COMPLETED", "Brew session completed", actor_id=user.id)
    audit(db, user.id, "BREW_SESSION_COMPLETED", "BrewSession", session.id)
    _bump(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, user: User, session_id: uuid.UUID) -> BrewSession:
    session = db.scalar(
        select(BrewSession).where(BrewSession.id == session_id, BrewSession.user_id == user.id)
    )
    if session is None:
        raise NotFoundError("Brew session not found")
    return session


def active_session(db: Session, user: User) -> BrewSession | None:
    session = db.scalar(
        select(BrewSession)
        .where(
            BrewSession.user_id == user.id,
            BrewSession.status.in_(("ACTIVE", "PAUSED")),
        )
        .order_by(BrewSession.started_at.desc())
    )
    if session:
        reconcile_reminders(db, session)
    return session


def start_mash(db: Session, user: User, session_id: uuid.UUID) -> BrewStage:
    session = get_session(db, user, session_id)
    if session.status != "ACTIVE":
        raise ConflictError("Brew session must be active before Mash starts")
    existing = first_mash_stage(db, session)
    if existing and existing.status not in {"PENDING"}:
        raise ConflictError("Mash has already been started")
    now = utc_now()
    if existing is None:
        stage = BrewStage(
            id=legacy_stage_instance_id(session.id, "MASH"),
            brew_session_id=session.id,
            name="MASH",
            status="ACTIVE",
            started_at=now,
            target_duration_seconds=session.planned_mash_duration_minutes * 60,
            target_temperature=session.target_mash_temperature,
            temperature_unit=session.mash_temperature_unit,
            target_ph=session.target_mash_ph,
            ph_tolerance=session.mash_ph_tolerance,
            target_gravity=session.target_mash_gravity,
            gravity_tolerance=session.mash_gravity_tolerance,
            canonical_stage_type="MASH",
            occurrence_number=1,
        )
        db.add(stage)
        db.flush()
    else:
        stage = existing
        stage.status = "ACTIVE"
        stage.started_at = now
        db.flush()
    timer = BrewTimer(
        brew_stage_id=stage.id,
        brew_session_id=session.id,
        started_at=now,
        planned_duration_seconds=stage.target_duration_seconds
        or session.planned_mash_duration_minutes * 60,
        deadline_at=now + timedelta(seconds=stage.target_duration_seconds or 0),
        clock_basis="WALL_CLOCK",
        timer_type="STAGE_PRIMARY",
    )
    reminder = Notification(
        brew_stage_id=stage.id,
        brew_session_id=session.id,
        notification_type="MASH_PH_DUE",
        message="Measure Mash pH",
        due_at=now,
        status="DUE",
    )
    db.add_all([timer, reminder])
    gravity_due_seconds = max(0, (stage.target_duration_seconds or 0) - 300)
    if gravity_due_seconds == 0:
        db.add(
            Notification(
                brew_stage_id=stage.id,
                brew_session_id=session.id,
                notification_type="MASH_GRAVITY_DUE",
                message="Measure Mash Gravity",
                due_at=now,
                status="DUE",
            )
        )
        journal(
            db,
            session.id,
            "BREW_MEASUREMENT_DUE",
            "Measure Mash Gravity",
            stage.id,
            {"type": "MASH_GRAVITY"},
            actor_id=user.id,
        )
    journal(db, session.id, "BREW_STAGE_STARTED", "Mash started", stage.id, actor_id=user.id)
    journal(db, session.id, "BREW_TIMER_STARTED", "Mash timer started", stage.id, actor_id=user.id)
    journal(
        db,
        session.id,
        "BREW_MEASUREMENT_DUE",
        "Measure Mash pH",
        stage.id,
        {"type": "MASH_PH"},
        actor_id=user.id,
    )
    audit(db, user.id, "BREW_STAGE_STARTED", "BrewStage", stage.id)
    _bump(session)
    db.commit()
    db.refresh(stage)
    return stage


def _stage_for_user(db: Session, user: User, stage_id: uuid.UUID) -> tuple[BrewStage, BrewSession]:
    row = db.execute(
        select(BrewStage, BrewSession)
        .join(BrewSession, BrewSession.id == BrewStage.brew_session_id)
        .where(BrewStage.id == stage_id, BrewSession.user_id == user.id)
    ).one_or_none()
    if row is None:
        raise NotFoundError("Brew stage not found")
    return row


def reconcile_reminders(db: Session, session: BrewSession) -> None:
    stage = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session.id,
            BrewStage.name.in_(("MASH",)),
            BrewStage.status == "ACTIVE",
        )
    )
    if not stage or not stage.started_at:
        return
    _project_timers(db, session)
    gravity = db.scalar(
        select(Notification).where(
            Notification.brew_stage_id == stage.id,
            Notification.notification_type == "MASH_GRAVITY_DUE",
        )
    )
    gravity_due_seconds = max(0, stage.target_duration_seconds - 300)
    gravity_due_at = _aware(stage.started_at) + timedelta(seconds=gravity_due_seconds)
    if gravity is None and utc_now() >= gravity_due_at:
        gravity = Notification(
            brew_stage_id=stage.id,
            brew_session_id=session.id,
            notification_type="MASH_GRAVITY_DUE",
            message="Measure Mash Gravity",
            due_at=utc_now(),
            status="DUE",
        )
        db.add(gravity)
        journal(
            db,
            session.id,
            "BREW_MEASUREMENT_DUE",
            "Measure Mash Gravity",
            stage.id,
            {"type": "MASH_GRAVITY"},
        )
        db.commit()


def _project_timers(db: Session, session: BrewSession) -> None:
    now = utc_now()
    timers = list(
        db.scalars(select(BrewTimer).where(BrewTimer.brew_session_id == session.id)).all()
    )
    if not timers:
        timers = list(
            db.scalars(
                select(BrewTimer)
                .join(BrewStage, BrewStage.id == BrewTimer.brew_stage_id)
                .where(BrewStage.brew_session_id == session.id)
            ).all()
        )
    for timer in timers:
        if timer.status != "RUNNING" or not timer.deadline_at:
            if timer.status == "RUNNING" and timer.planned_duration_seconds:
                elapsed = timer_elapsed_seconds(timer, now)
                if elapsed >= timer.planned_duration_seconds:
                    timer.status = "EXPIRED"
                    timer.expired_at = timer.deadline_at or now
            continue
        if now >= _aware(timer.deadline_at) and timer.status == "RUNNING":
            timer.status = "EXPIRED"
            timer.expired_at = timer.deadline_at


def _measurement_rule(stage: BrewStage, kind: str) -> tuple[Decimal, Decimal, str, str]:
    if kind == "MASH_PH":
        return stage.target_ph, stage.ph_tolerance, "pH", "0.001"
    if kind in {"MASH_GRAVITY", "POST_MASH_GRAVITY"}:
        return stage.target_gravity, stage.gravity_tolerance, "SG", "0.001"
    if kind in {
        "MASH_IN_TEMPERATURE",
        "MASH_REST_TEMPERATURE",
        "KNOCKOUT_TEMPERATURE",
        "PITCH_TEMPERATURE",
    }:
        return stage.target_temperature, Decimal("2.0"), "degC", "0.1"
    if kind in {"PRE_BOIL_GRAVITY", "ORIGINAL_GRAVITY"}:
        return stage.target_gravity, stage.gravity_tolerance, "SG", "0.001"
    if kind in {"PRE_BOIL_VOLUME", "KNOCKOUT_VOLUME"}:
        return Decimal("0"), Decimal("0"), "L", "0.001"
    raise DomainError("Unsupported measurement type")


def record_measurement(
    db: Session, user: User, stage_id: uuid.UUID, command: MeasurementCommand
) -> tuple[Measurement, Deviation | None]:
    stage, session = _stage_for_user(db, user, stage_id)
    operation_id = getattr(command, "operation_id", None)
    document = {
        "stage_id": str(stage_id),
        "measurement_type": command.measurement_type,
        "value": str(command.value),
        "unit": command.unit,
        "note": command.note,
        "instrument": command.instrument,
        "entry_method": getattr(command, "entry_method", None) or "MANUAL",
        "late_entry_reason": getattr(command, "late_entry_reason", None),
    }
    replay = replay_or_conflict(
        db, user.id, "record_measurement", "BrewStage", stage.id, operation_id, document
    )
    if replay and replay.result_resource_id:
        found = db.get(Measurement, replay.result_resource_id)
        if found:
            deviation = db.scalar(select(Deviation).where(Deviation.measurement_id == found.id))
            return found, deviation
    if session.status == "PAUSED":
        raise ConflictError("Normal measurements cannot be recorded while the session is paused")
    if session.status == "ABORTED":
        raise ConflictError(
            "New measurements are prohibited on an aborted session",
            code="TERMINAL_SESSION_EVIDENCE_PROHIBITED",
        )
    late_reason = getattr(command, "late_entry_reason", None)
    late = False
    if stage.status == "COMPLETED":
        if not late_reason or len(late_reason) < 10:
            raise DomainError("Late measurement requires a reason of at least 10 characters", 422)
        boundary = stage.completed_at
        if session.status == "COMPLETED":
            boundary = session.completed_at
        if boundary and utc_now() > _aware(boundary) + timedelta(hours=24):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
        late = True
    elif stage.status != "ACTIVE" or session.status != "ACTIVE":
        raise ConflictError("Measurements can only be recorded on an active stage")
    target, tolerance, expected_unit, precision = _measurement_rule(stage, command.measurement_type)
    if command.unit != expected_unit:
        raise DomainError(f"{command.measurement_type} must use unit {expected_unit}")
    existing = db.scalar(
        select(Measurement).where(
            Measurement.brew_stage_id == stage.id,
            Measurement.measurement_type == command.measurement_type,
            Measurement.correction_of_id.is_(None),
        )
    )
    if existing:
        raise ConflictError("Measurement already recorded; use an auditable correction")
    measured_at = command.measured_at or utc_now()
    now = utc_now()
    if measured_at > now + timedelta(minutes=5):
        raise DomainError("observed_at cannot be more than five minutes in the future", 422)
    entry_method = getattr(command, "entry_method", None) or "MANUAL"
    measurement = Measurement(
        brew_stage_id=stage.id,
        measurement_type=command.measurement_type,
        value=command.value,
        unit=command.unit,
        measured_at=measured_at,
        note=command.note,
        instrument=command.instrument,
        provenance="BREWER",
        process_point="MASH" if "MASH" in command.measurement_type else command.measurement_type,
        raw_value=command.value,
        raw_unit=command.unit,
        canonical_value=command.value,
        canonical_unit=expected_unit,
        recorded_at=now,
        entry_method=entry_method,
        actor_user_id=user.id,
        definition_version="phase3-measurement-v1",
        late_entry=late,
        late_entry_reason=late_reason,
        available_at_original_stage_completion=not late,
        available_at_original_session_completion=session.status != "COMPLETED",
        operation_id=operation_id,
    )
    db.add(measurement)
    db.flush()
    comparison = compare_measurement(target, command.value, tolerance, precision)
    planned = planned_versus_actual(target, command.value, tolerance, expected_unit, precision)
    deviation = None
    if comparison.outside_tolerance:
        deviation = Deviation(
            measurement_id=measurement.id,
            brew_session_id=session.id,
            brew_stage_id=stage.id,
            target_value=target,
            actual_value=command.value,
            variance=comparison.variance,
            tolerance=tolerance,
            unit=expected_unit,
            comparison_status=planned.status,
        )
        db.add(deviation)
    reminder = db.scalar(
        select(Notification).where(
            Notification.brew_stage_id == stage.id,
            Notification.notification_type == f"{command.measurement_type}_DUE",
        )
    )
    if reminder:
        prior = reminder.status
        reminder.status = "COMPLETED"
        reminder.acknowledged_at = reminder.acknowledged_at or now
        reminder.completed_at = now
        reminder.satisfaction_source_type = "Measurement"
        reminder.satisfaction_source_id = measurement.id
        db.add(
            BrewReminderHistory(
                reminder_id=reminder.id,
                prior_status=prior,
                new_status="COMPLETED",
                cause="AUTHORITATIVE_MEASUREMENT",
                actor_user_id=user.id,
            )
        )
    requirement = db.scalar(
        select(BrewStageRequirement).where(
            BrewStageRequirement.stage_instance_id == stage.id,
            BrewStageRequirement.requirement_class == "MEASUREMENT",
            BrewStageRequirement.status.in_(("PENDING", "DUE", "WAIVED")),
        )
    )
    matching = None
    for item in db.scalars(
        select(BrewStageRequirement).where(
            BrewStageRequirement.stage_instance_id == stage.id,
            BrewStageRequirement.requirement_class == "MEASUREMENT",
        )
    ):
        key = (item.payload or {}).get("definition_key")
        if key == command.measurement_type:
            matching = item
            break
    requirement = matching or requirement
    if requirement:
        if requirement.status == "WAIVED":
            waiver = db.scalar(
                select(BrewWaiver).where(
                    BrewWaiver.requirement_id == requirement.requirement_id,
                    BrewWaiver.status == "ACTIVE",
                )
            )
            if waiver:
                waiver.status = "SUPERSEDED_BY_EVIDENCE"
                waiver.superseded_by_id = measurement.id
                waiver.superseded_by_type = "Measurement"
        requirement.status = "SATISFIED"
        requirement.satisfaction_source_type = "Measurement"
        requirement.satisfaction_source_id = measurement.id
        measurement.requirement_id = requirement.requirement_id
    journal(
        db,
        session.id,
        "BREW_MEASUREMENT_RECORDED",
        (
            f"{command.measurement_type.replace('_', ' ').title()} recorded: "
            f"{command.value} {command.unit}"
        ),
        stage.id,
        {"measurement_id": str(measurement.id), "type": command.measurement_type},
        actor_id=user.id,
        operation_id=operation_id,
    )
    if deviation:
        journal(
            db,
            session.id,
            "BREW_VARIANCE_DETECTED",
            f"{command.measurement_type.replace('_', ' ').title()} outside tolerance",
            stage.id,
            {"measurement_id": str(measurement.id), "variance": str(comparison.variance)},
            actor_id=user.id,
        )
    audit(db, user.id, "BREW_MEASUREMENT_RECORDED", "Measurement", measurement.id)
    _bump(session)
    store_success(
        db,
        user.id,
        "record_measurement",
        "BrewStage",
        stage.id,
        operation_id,
        document,
        {"id": str(measurement.id), "type": measurement.measurement_type},
        "Measurement",
        measurement.id,
        http_status=201,
    )
    db.commit()
    db.refresh(measurement)
    if deviation:
        db.refresh(deviation)
    reconcile_reminders(db, session)
    return measurement, deviation


def correct_measurement(
    db: Session, user: User, measurement_id: uuid.UUID, command: MeasurementCommand
) -> Measurement:
    row = db.execute(
        select(Measurement, BrewStage, BrewSession)
        .join(BrewStage, BrewStage.id == Measurement.brew_stage_id)
        .join(BrewSession, BrewSession.id == BrewStage.brew_session_id)
        .where(Measurement.id == measurement_id, BrewSession.user_id == user.id)
    ).one_or_none()
    if row is None:
        raise NotFoundError("Measurement not found")
    original, stage, session = row
    if command.measurement_type != original.measurement_type:
        raise DomainError("A correction must preserve the measurement type")
    _, _, expected_unit, _ = _measurement_rule(stage, command.measurement_type)
    if command.unit != expected_unit:
        raise DomainError(f"Correction must use unit {expected_unit}")
    if session.status in {"COMPLETED", "ABORTED"} and session.completed_at:
        if utc_now() > _aware(session.completed_at or session.aborted_at) + timedelta(days=30):
            raise ConflictError("Late entry window has closed", code="LATE_ENTRY_WINDOW_CLOSED")
    correction = Measurement(
        brew_stage_id=stage.id,
        measurement_type=original.measurement_type,
        value=command.value,
        unit=command.unit,
        measured_at=command.measured_at or utc_now(),
        note=command.note or "Auditable correction",
        instrument=command.instrument,
        provenance="BREWER_CORRECTION",
        correction_of_id=original.id,
        process_point=original.process_point,
        raw_value=command.value,
        raw_unit=command.unit,
        canonical_value=command.value,
        canonical_unit=expected_unit,
        recorded_at=utc_now(),
        entry_method="MANUAL",
        actor_user_id=user.id,
        definition_version="phase3-measurement-v1",
    )
    db.add(correction)
    db.flush()
    journal(
        db,
        session.id,
        "BREW_MEASUREMENT_CORRECTED",
        f"Correction appended for {original.measurement_type}",
        stage.id,
        {"original_id": str(original.id), "correction_id": str(correction.id)},
        actor_id=user.id,
    )
    audit(
        db,
        user.id,
        "BREW_MEASUREMENT_CORRECTED",
        "Measurement",
        correction.id,
        {"original_id": str(original.id)},
    )
    _bump(session)
    db.commit()
    db.refresh(correction)
    return correction


def complete_mash(db: Session, user: User, stage_id: uuid.UUID) -> BrewStage:
    stage, session = _stage_for_user(db, user, stage_id)
    if stage.status != "ACTIVE":
        raise ConflictError("Mash is not active")
    kinds = set(
        db.scalars(
            select(Measurement.measurement_type).where(Measurement.brew_stage_id == stage.id)
        ).all()
    )
    required = {"MASH_PH", "MASH_GRAVITY"}
    if not is_legacy_plan(session) and "POST_MASH_GRAVITY" in kinds:
        required = {"MASH_PH", "POST_MASH_GRAVITY"}
    missing = required - kinds
    if missing:
        raise DomainError(f"Required measurements missing: {', '.join(sorted(missing))}")
    now = utc_now()
    stage.status = "COMPLETED"
    stage.completed_at = now
    timer = db.scalar(select(BrewTimer).where(BrewTimer.brew_stage_id == stage.id))
    if timer and timer.status not in {"COMPLETED", "CANCELLED"}:
        timer.status = "COMPLETED"
        timer.completed_at = now
    journal(db, session.id, "BREW_STAGE_COMPLETED", "Mash completed", stage.id, actor_id=user.id)
    audit(db, user.id, "BREW_STAGE_COMPLETED", "BrewStage", stage.id)
    if is_legacy_plan(session):
        complete = db.scalar(
            select(BrewStage).where(
                BrewStage.brew_session_id == session.id,
                BrewStage.canonical_stage_type == "BREW_COMPLETE",
            )
        )
        if complete:
            complete.status = "COMPLETED"
            complete.completed_at = now
        session.status = "COMPLETED"
        session.completed_at = now
        journal(
            db, session.id, "BREW_SESSION_COMPLETED", "Brew session completed", actor_id=user.id
        )
    _bump(session)
    db.commit()
    db.refresh(stage)
    return stage


def timer_elapsed_seconds(timer: BrewTimer, now: datetime | None = None) -> int:
    current = now or utc_now()
    endpoint = timer.completed_at or timer.paused_at or current
    return max(
        0,
        int((_aware(endpoint) - _aware(timer.started_at)).total_seconds())
        - timer.accumulated_pause_seconds,
    )


def session_details(db: Session, user: User, session_id: uuid.UUID) -> dict:
    from brewing_api.application.phase3.media import reconcile_orphans

    session = get_session(db, user, session_id)
    reconcile_reminders(db, session)
    reconcile_orphans()
    version = db.get(RecipeVersion, session.recipe_version_id)
    stages = list(
        db.scalars(
            select(BrewStage)
            .where(BrewStage.brew_session_id == session.id)
            .order_by(BrewStage.created_at, BrewStage.occurrence_number)
        ).all()
    )
    mash_candidates = [
        item for item in stages if item.name == "MASH" or item.canonical_stage_type == "MASH"
    ]
    stage = next((item for item in mash_candidates if item.status != "PENDING"), None)
    timer = None
    measurements: list[Measurement] = []
    deviations: list[Deviation] = []
    notifications: list[Notification] = []
    if stage:
        timer = db.scalar(select(BrewTimer).where(BrewTimer.brew_stage_id == stage.id))
        measurements = list(
            db.scalars(
                select(Measurement)
                .where(Measurement.brew_stage_id == stage.id)
                .order_by(Measurement.created_at)
            ).all()
        )
        if measurements:
            deviations = list(
                db.scalars(
                    select(Deviation).where(
                        Deviation.measurement_id.in_([item.id for item in measurements])
                    )
                ).all()
            )
        notifications = list(
            db.scalars(
                select(Notification)
                .where(Notification.brew_stage_id == stage.id)
                .order_by(Notification.due_at)
            ).all()
        )
    all_notifications = list(
        db.scalars(
            select(Notification)
            .join(BrewStage, BrewStage.id == Notification.brew_stage_id)
            .where(BrewStage.brew_session_id == session.id)
            .order_by(Notification.due_at)
        ).all()
    )
    events = list(
        db.scalars(
            select(BrewJournalEvent)
            .where(BrewJournalEvent.brew_session_id == session.id)
            .order_by(BrewJournalEvent.created_at, BrewJournalEvent.id)
        ).all()
    )
    timers = list(
        db.scalars(
            select(BrewTimer)
            .join(BrewStage, BrewStage.id == BrewTimer.brew_stage_id)
            .where(BrewStage.brew_session_id == session.id)
        ).all()
    )
    notes = list(db.scalars(select(BrewNote).where(BrewNote.brew_session_id == session.id)).all())
    attachments = list(
        db.scalars(select(BrewAttachment).where(BrewAttachment.brew_session_id == session.id)).all()
    )
    additions = list(
        db.scalars(
            select(BrewAdditionEvent).where(BrewAdditionEvent.brew_session_id == session.id)
        ).all()
    )
    waivers = list(
        db.scalars(select(BrewWaiver).where(BrewWaiver.brew_session_id == session.id)).all()
    )
    plan_steps = list(
        db.scalars(
            select(BrewPlanStep)
            .where(BrewPlanStep.brew_session_id == session.id)
            .order_by(BrewPlanStep.sort_index)
        ).all()
    )
    requirements = list(
        db.scalars(
            select(BrewStageRequirement).where(BrewStageRequirement.brew_session_id == session.id)
        ).all()
    )
    current = next((item for item in stages if item.status in {"ACTIVE", "PAUSED"}), None)
    due = [item for item in all_notifications if item.status in {"DUE", "EXPIRED"}]
    next_action = None
    if current is None and session.status == "ACTIVE":
        pending = next((item for item in stages if item.status == "PENDING"), None)
        if pending:
            next_action = f"Start {pending.name}"
    elif due:
        next_action = due[0].message
    elif current:
        next_action = f"Continue {current.name}"
    return {
        "session": session,
        "version": version,
        "stage": stage,
        "stages": stages,
        "plan_steps": plan_steps,
        "current_stage": current,
        "timer": timer,
        "timers": timers,
        "timer_elapsed_seconds": timer_elapsed_seconds(timer) if timer else None,
        "measurements": measurements,
        "deviations": deviations,
        "notifications": notifications,
        "all_notifications": all_notifications,
        "notes": notes,
        "attachments": attachments,
        "additions": additions,
        "waivers": waivers,
        "requirements": requirements,
        "next_required_action": next_action,
        "journal": events,
    }
