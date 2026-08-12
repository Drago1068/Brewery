import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from calculations import compare_measurement
from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.application.errors import ConflictError, DomainError, NotFoundError
from brewing_api.application.events import audit, journal
from brewing_api.application.recipes import get_owned_version
from brewing_api.domain.audit.models import BrewJournalEvent
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


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def start_session(db: Session, user: User, version_id: uuid.UUID) -> BrewSession:
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
    audit(db, user.id, "BREW_SESSION_PLANNED", "BrewSession", session.id)
    db.commit()
    db.refresh(session)
    return session


def activate_session(db: Session, user: User, session_id: uuid.UUID) -> BrewSession:
    session = get_session(db, user, session_id)
    if session.status != "PLANNED":
        raise ConflictError("Only a planned brew session can be started")
    session.status = "READY"
    db.flush()
    session.status = "ACTIVE"
    session.started_at = utc_now()
    journal(db, session.id, "BREW_SESSION_STARTED", "Brew session started")
    audit(db, user.id, "BREW_SESSION_STARTED", "BrewSession", session.id)
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
        .where(BrewSession.user_id == user.id, BrewSession.status == "ACTIVE")
        .order_by(BrewSession.started_at.desc())
    )
    if session:
        reconcile_reminders(db, session)
    return session


def start_mash(db: Session, user: User, session_id: uuid.UUID) -> BrewStage:
    session = get_session(db, user, session_id)
    if session.status != "ACTIVE":
        raise ConflictError("Brew session must be active before Mash starts")
    existing = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session.id, BrewStage.name == "MASH"
        )
    )
    if existing:
        raise ConflictError("Mash has already been started")
    now = utc_now()
    stage = BrewStage(
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
    )
    db.add(stage)
    db.flush()
    timer = BrewTimer(
        brew_stage_id=stage.id,
        started_at=now,
        planned_duration_seconds=stage.target_duration_seconds,
    )
    reminder = Notification(
        brew_stage_id=stage.id,
        notification_type="MASH_PH_DUE",
        message="Measure Mash pH",
        due_at=now,
    )
    db.add_all([timer, reminder])
    journal(db, session.id, "BREW_STAGE_STARTED", "Mash started", stage.id)
    journal(db, session.id, "BREW_TIMER_STARTED", "Mash timer started", stage.id)
    journal(
        db,
        session.id,
        "BREW_MEASUREMENT_DUE",
        "Measure Mash pH",
        stage.id,
        {"type": "MASH_PH"},
    )
    audit(db, user.id, "BREW_STAGE_STARTED", "BrewStage", stage.id)
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
            BrewStage.name == "MASH",
            BrewStage.status == "ACTIVE",
        )
    )
    if not stage or not stage.started_at:
        return
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
            notification_type="MASH_GRAVITY_DUE",
            message="Measure Mash Gravity",
            due_at=utc_now(),
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


def _measurement_rule(stage: BrewStage, kind: str) -> tuple[Decimal, Decimal, str, str]:
    if kind == "MASH_PH":
        return stage.target_ph, stage.ph_tolerance, "pH", "0.001"
    if kind == "MASH_GRAVITY":
        return stage.target_gravity, stage.gravity_tolerance, "SG", "0.001"
    raise DomainError("Unsupported measurement type")


def record_measurement(
    db: Session, user: User, stage_id: uuid.UUID, command: MeasurementCommand
) -> tuple[Measurement, Deviation | None]:
    stage, session = _stage_for_user(db, user, stage_id)
    if stage.status != "ACTIVE":
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
    measurement = Measurement(
        brew_stage_id=stage.id,
        measurement_type=command.measurement_type,
        value=command.value,
        unit=command.unit,
        measured_at=measured_at,
        note=command.note,
        instrument=command.instrument,
        provenance="BREWER",
    )
    db.add(measurement)
    db.flush()
    comparison = compare_measurement(target, command.value, tolerance, precision)
    deviation = None
    if comparison.outside_tolerance:
        deviation = Deviation(
            measurement_id=measurement.id,
            target_value=target,
            actual_value=command.value,
            variance=comparison.variance,
            tolerance=tolerance,
            unit=expected_unit,
        )
        db.add(deviation)
    reminder = db.scalar(
        select(Notification).where(
            Notification.brew_stage_id == stage.id,
            Notification.notification_type == f"{command.measurement_type}_DUE",
        )
    )
    if reminder:
        reminder.status = "ACKNOWLEDGED"
        reminder.acknowledged_at = utc_now()
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
    )
    if deviation:
        journal(
            db,
            session.id,
            "BREW_VARIANCE_DETECTED",
            f"{command.measurement_type.replace('_', ' ').title()} outside tolerance",
            stage.id,
            {"measurement_id": str(measurement.id), "variance": str(comparison.variance)},
        )
    audit(db, user.id, "BREW_MEASUREMENT_RECORDED", "Measurement", measurement.id)
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
    )
    audit(
        db,
        user.id,
        "BREW_MEASUREMENT_CORRECTED",
        "Measurement",
        correction.id,
        {"original_id": str(original.id)},
    )
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
    missing = {"MASH_PH", "MASH_GRAVITY"} - kinds
    if missing:
        raise DomainError(f"Required measurements missing: {', '.join(sorted(missing))}")
    now = utc_now()
    stage.status = "COMPLETED"
    stage.completed_at = now
    timer = db.scalar(select(BrewTimer).where(BrewTimer.brew_stage_id == stage.id))
    if timer:
        timer.status = "COMPLETED"
        timer.completed_at = now
    session.status = "COMPLETED"
    session.completed_at = now
    journal(db, session.id, "BREW_STAGE_COMPLETED", "Mash completed", stage.id)
    audit(db, user.id, "BREW_STAGE_COMPLETED", "BrewStage", stage.id)
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
    session = get_session(db, user, session_id)
    reconcile_reminders(db, session)
    version = db.get(RecipeVersion, session.recipe_version_id)
    stage = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session.id, BrewStage.name == "MASH"
        )
    )
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
    events = list(
        db.scalars(
            select(BrewJournalEvent)
            .where(BrewJournalEvent.brew_session_id == session.id)
            .order_by(BrewJournalEvent.created_at)
        ).all()
    )
    return {
        "session": session,
        "version": version,
        "stage": stage,
        "timer": timer,
        "timer_elapsed_seconds": timer_elapsed_seconds(timer) if timer else None,
        "measurements": measurements,
        "deviations": deviations,
        "notifications": notifications,
        "journal": events,
    }
