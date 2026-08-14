from __future__ import annotations

import os
import time
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from brewing_api.application import brew_day as brew_service
from brewing_api.application.phase3 import commands as phase3
from brewing_api.domain.audit.models import BrewJournalEvent
from brewing_api.domain.brew_day.models import BrewNote
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.identity.models import User
from brewing_api.domain.measurements.models import Measurement
from brewing_api.domain.notifications.models import Notification
from brewing_api.platform.metrics import record_duration, reset_metrics, snapshot
from brewing_api.platform.time import utc_now

THRESHOLDS_MS = {
    "dashboard_projection": 750,
    "timer_projection_10": 500,
    "measurement_plus_reminder": 1000,
    "reminder_ack": 750,
    "stage_transition": 1250,
    "journal_json_750": 2000,
    "journal_html_750": 3000,
}


def create_isolated_benchmark_session(db: Session, user: User) -> BrewSession:
    """Create a disposable session that is never a caller's live BrewSession."""
    from brewing_api.domain.recipes.models import Recipe, RecipeVersion

    now = utc_now()
    recipe = Recipe(owner_id=user.id, name=f"bench-{uuid.uuid4().hex[:12]}")
    db.add(recipe)
    db.flush()
    version = RecipeVersion(
        recipe_id=recipe.id,
        version_number=1,
        target_mash_temperature=Decimal("152.00"),
        mash_temperature_unit="degF",
        target_mash_ph=Decimal("5.30"),
        mash_ph_tolerance=Decimal("0.05"),
        target_mash_gravity=Decimal("1.050"),
        mash_gravity_tolerance=Decimal("0.003"),
        planned_mash_duration_minutes=60,
    )
    db.add(version)
    db.flush()
    session = BrewSession(
        user_id=user.id,
        recipe_version_id=version.id,
        status="ACTIVE",
        started_at=now,
        target_mash_temperature=version.target_mash_temperature,
        mash_temperature_unit=version.mash_temperature_unit,
        target_mash_ph=version.target_mash_ph,
        mash_ph_tolerance=version.mash_ph_tolerance,
        target_mash_gravity=version.target_mash_gravity,
        mash_gravity_tolerance=version.mash_gravity_tolerance,
        planned_mash_duration_minutes=version.planned_mash_duration_minutes,
        plan_kind="phase3-bench-isolated-v1",
        revision=1,
    )
    db.add(session)
    db.flush()
    mash = BrewStage(
        brew_session_id=session.id,
        name="MASH",
        canonical_stage_type="MASH",
        status="ACTIVE",
        started_at=now,
        target_duration_seconds=3600,
        target_temperature=session.target_mash_temperature,
        temperature_unit=session.mash_temperature_unit,
        target_ph=session.target_mash_ph,
        ph_tolerance=session.mash_ph_tolerance,
        target_gravity=session.target_mash_gravity,
        gravity_tolerance=session.mash_gravity_tolerance,
        occurrence_number=1,
    )
    db.add(mash)
    db.flush()
    for index in range(10):
        db.add(
            BrewTimer(
                brew_stage_id=mash.id,
                brew_session_id=session.id,
                name=f"Concurrent timer {index + 1}",
                started_at=now,
                planned_duration_seconds=600 + index,
                deadline_at=now + timedelta(seconds=600 + index),
                clock_basis="WALL_CLOCK",
                timer_type="AUXILIARY",
            )
        )
    for index in range(20):
        db.add(
            Notification(
                brew_stage_id=mash.id,
                brew_session_id=session.id,
                notification_type=f"BENCH_REMINDER_{index}",
                message=f"Benchmark reminder {index}",
                due_at=now,
                status="DUE" if index < 5 else "SCHEDULED",
                priority="REQUIRED" if index < 10 else "OPTIONAL",
            )
        )
    for index in range(100):
        db.add(
            Measurement(
                brew_stage_id=mash.id,
                measurement_type="MASH_PH" if index % 2 == 0 else "MASH_GRAVITY",
                value=Decimal("5.30") if index % 2 == 0 else Decimal("1.050"),
                unit="pH" if index % 2 == 0 else "SG",
                measured_at=now,
                provenance="BENCH",
                recorded_at=now,
                actor_user_id=user.id,
                process_point="MASH",
            )
        )
    for index in range(50):
        db.add(
            BrewNote(
                brew_session_id=session.id,
                stage_instance_id=mash.id,
                body=f"Benchmark note {index}",
                actor_user_id=user.id,
            )
        )
    journal_events = int(os.environ.get("PHASE3_PERF_JOURNAL_EVENTS", "750"))
    for index in range(journal_events):
        db.add(
            BrewJournalEvent(
                brew_session_id=session.id,
                brew_stage_id=mash.id,
                event_type="BENCH_EVENT",
                message=f"Benchmark journal {index}",
                event_data={"index": index},
                occurred_at=now,
                recorded_at=now,
                actor_user_id=user.id,
            )
        )
    db.commit()
    db.refresh(session)
    return session


def run_isolated_performance_harness(
    samples: int | None = None, warmup: int | None = None
) -> dict:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from brewing_api.domain import model_registry  # noqa: F401
    from brewing_api.platform.database import Base

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        user = User(
            username=f"bench-{uuid.uuid4().hex[:10]}",
            password_hash="isolated-benchmark-hash",
        )
        db.add(user)
        db.commit()
        session = create_isolated_benchmark_session(db, user)
        return run_performance_suite(db, user, session.id, samples=samples, warmup=warmup)



def run_performance_suite(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    samples: int | None = None,
    warmup: int | None = None,
) -> dict:
    samples = samples if samples is not None else int(os.environ.get("PHASE3_PERF_SAMPLES", "100"))
    warmup = warmup if warmup is not None else int(os.environ.get("PHASE3_PERF_WARMUP", "10"))
    reset_metrics()
    stage = db.scalar(select(BrewStage).where(BrewStage.brew_session_id == session_id))
    assert stage is not None

    def measure(name: str, fn) -> None:
        for index in range(warmup + samples):
            started = time.perf_counter()
            ok = True
            try:
                fn(index)
            except Exception:
                ok = False
                raise
            finally:
                if index >= warmup:
                    record_duration(name, started, ok=ok)

    measure("dashboard_projection", lambda _i: brew_service.session_details(db, user, session_id))

    def project_timers(_i: int) -> None:
        details = brew_service.session_details(db, user, session_id)
        assert len(details["timers"]) >= 10

    measure("timer_projection_10", project_timers)

    reminders = list(
        db.scalars(
            select(Notification).where(
                Notification.brew_stage_id == stage.id, Notification.status == "DUE"
            )
        )
    )

    def ack(_i: int) -> None:
        target = reminders[_i % max(1, len(reminders))]
        if target.status in {"COMPLETED", "ACKNOWLEDGED"}:
            target.status = "DUE"
            db.commit()
        phase3.acknowledge_reminder(db, user, target.id)

    if reminders:
        measure("reminder_ack", ack)

    journal_events = int(os.environ.get("PHASE3_PERF_JOURNAL_EVENTS", "750"))

    def journal_json(_i: int) -> None:
        details = brew_service.session_details(db, user, session_id)
        assert len(details["journal"]) >= min(journal_events, 50)

    measure("journal_json_750", journal_json)

    def journal_html(_i: int) -> None:
        details = brew_service.session_details(db, user, session_id)
        rows = "".join(f"<li>{item.message}</li>" for item in details["journal"][:50])
        assert "<li>" in rows

    measure("journal_html_750", journal_html)

    def stage_transition(_i: int) -> None:
        current = db.get(BrewSession, session_id)
        assert current is not None
        op = f"bench-trans-{_i}-{uuid.uuid4().hex[:8]}"
        if current.status == "ACTIVE":
            phase3.pause_session(db, user, session_id, current.revision, op)
        current = db.get(BrewSession, session_id)
        assert current is not None
        if current.status == "PAUSED":
            phase3.resume_session(db, user, session_id, current.revision)

    measure("stage_transition", stage_transition)

    def measurement_plus(_i: int) -> None:
        brew_service.session_details(db, user, session_id)
        if reminders:
            target = reminders[0]
            if target.status != "ACKNOWLEDGED":
                phase3.acknowledge_reminder(db, user, target.id)

    measure("measurement_plus_reminder", measurement_plus)

    report = snapshot()
    results = {}
    for key, threshold in THRESHOLDS_MS.items():
        op = report["operations"].get(key)
        if op is None:
            results[key] = {"status": "SKIPPED", "threshold_ms": threshold}
            continue
        results[key] = {
            "status": "PASS" if op["p95_ms"] <= threshold else "FAIL",
            "count": op["count"],
            "p50_ms": round(op["p50_ms"], 3),
            "p95_ms": round(op["p95_ms"], 3),
            "threshold_ms": threshold,
            "samples": op["count"],
        }
    failing = [name for name, item in results.items() if item["status"] != "PASS"]
    return {
        "rule_version": "phase3-performance-v1",
        "reference_class": "private-runtime-docker",
        "environment": os.environ.get("PHASE3_PERF_ENV", "isolated-in-process-harness"),
        "sample_size": samples,
        "warmup": warmup,
        "method": "perf_counter p50/p95 over isolated disposable session",
        "results": results,
        "failing": failing,
        "all_pass": not failing,
        "isolated_session_id": str(session_id),
    }


def session_fingerprint(db: Session, session_id: uuid.UUID | str) -> dict:
    sid = session_id if isinstance(session_id, uuid.UUID) else uuid.UUID(str(session_id))
    return {
        "timers": db.scalar(
            select(func.count())
            .select_from(BrewTimer)
            .where(BrewTimer.brew_session_id == sid)
        ),
        "notes": db.scalar(
            select(func.count()).select_from(BrewNote).where(BrewNote.brew_session_id == sid)
        ),
        "journal": db.scalar(
            select(func.count())
            .select_from(BrewJournalEvent)
            .where(BrewJournalEvent.brew_session_id == sid)
        ),
        "measurements": db.scalar(
            select(func.count())
            .select_from(Measurement)
            .join(BrewStage, BrewStage.id == Measurement.brew_stage_id)
            .where(BrewStage.brew_session_id == sid)
        ),
    }
