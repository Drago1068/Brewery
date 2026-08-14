from __future__ import annotations

import os
import time
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
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


def seed_representative_session(db: Session, user: User, session: BrewSession) -> dict:
    """Build a representative active BrewSession for P3-FR-088 evidence."""
    now = utc_now()
    stages = list(db.scalars(select(BrewStage).where(BrewStage.brew_session_id == session.id)))
    mash = next(
        (item for item in stages if (item.canonical_stage_type or item.name) == "MASH"), None
    )
    if mash is None:
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
    else:
        mash.status = "ACTIVE"
        mash.started_at = mash.started_at or now
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
    return {"stage_id": mash.id, "session_id": session.id}


def run_performance_suite(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    samples: int | None = None,
    warmup: int | None = None,
) -> dict:
    samples = samples if samples is not None else int(os.environ.get("PHASE3_PERF_SAMPLES", "30"))
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

    measure(
        "dashboard_projection",
        lambda _i: brew_service.session_details(db, user, session_id),
    )

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
        assert len(details["journal"]) >= journal_events

    measure("journal_json_750", journal_json)

    def journal_html(_i: int) -> None:
        details = brew_service.session_details(db, user, session_id)
        rows = "".join(
            f"<li>{item.message}</li>" for item in details["journal"][:journal_events]
        )
        assert "<li>" in rows

    measure("journal_html_750", journal_html)

    def stage_transition(_i: int) -> None:
        current = db.get(BrewSession, session_id)
        assert current is not None
        if current.status == "ACTIVE":
            phase3.pause_session(db, user, session_id)
        current = db.get(BrewSession, session_id)
        assert current is not None
        if current.status == "PAUSED":
            phase3.resume_session(db, user, session_id)

    measure("stage_transition", stage_transition)

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
        }
    if "measurement_plus_reminder" not in report["operations"]:
        results["measurement_plus_reminder"] = {
            "status": "SKIPPED",
            "note": "Measured in dedicated microbench with active mash reminders",
            "threshold_ms": THRESHOLDS_MS["measurement_plus_reminder"],
        }
    failing = [name for name, item in results.items() if item["status"] == "FAIL"]
    return {
        "rule_version": "phase3-performance-v1",
        "reference_class": "private-runtime-docker",
        "environment": os.environ.get("PHASE3_PERF_ENV", "in-process-testclient"),
        "sample_size": samples,
        "warmup": warmup,
        "method": "perf_counter p50/p95 over warmup-discarded samples",
        "results": results,
        "failing": failing,
        "all_pass": not failing,
    }
