from __future__ import annotations

import json
import os
import platform
import time
import uuid
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, event, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from brewing_api.application import brew_day as brew_service
from brewing_api.application.phase3 import commands as phase3
from brewing_api.application.phase3.plan import build_plan, persist_plan
from brewing_api.domain.audit.models import BrewJournalEvent
from brewing_api.domain.brew_day.models import (
    BrewAdditionCorrection,
    BrewAdditionEvent,
    BrewAttachment,
    BrewNote,
    BrewStageRequirement,
)
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage, BrewTimer
from brewing_api.domain.identity.models import User
from brewing_api.domain.ingredients.models import Ingredient
from brewing_api.domain.measurements.models import Measurement
from brewing_api.domain.notifications.models import Notification
from brewing_api.domain.recipes.models import (
    Recipe,
    RecipeIngredient,
    RecipeProcessStep,
    RecipeVersion,
)
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

REPRESENTATIVE_COUNTS = {
    "canonical_plan_steps": 13,
    "repeated_occurrences": 3,
    "timers": 10,
    "reminders": 20,
    "measurements": 100,
    "additions": 100,
    "notes": 50,
    "attachment_metadata": 20,
    "journal_events": 750,
}

REQUIRED_THROUGH_PITCH = (
    "MASH",
    "LAUTER_SPARGE",
    "BOIL",
    "WHIRLPOOL_FLAMEOUT",
    "CHILL",
    "YEAST_PITCH",
)


def _journal_event_target() -> int:
    return int(
        os.environ.get("PHASE3_PERF_JOURNAL_EVENTS", str(REPRESENTATIVE_COUNTS["journal_events"]))
    )


def describe_benchmark_dataset(db: Session, session_id: uuid.UUID) -> dict:
    stages = list(
        db.scalars(select(BrewStage).where(BrewStage.brew_session_id == session_id)).all()
    )
    canonical = sorted(
        {
            item.canonical_stage_type or item.name
            for item in stages
            if item.occurrence_number == 1
        }
    )
    repeats = sum(1 for item in stages if item.occurrence_number > 1)
    timers = db.scalar(
        select(func.count()).select_from(BrewTimer).where(BrewTimer.brew_session_id == session_id)
    )
    reminders = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.brew_session_id == session_id)
    )
    measurements = db.scalar(
        select(func.count())
        .select_from(Measurement)
        .where(Measurement.brew_session_id == session_id)
    )
    additions = db.scalar(
        select(func.count())
        .select_from(BrewAdditionEvent)
        .where(BrewAdditionEvent.brew_session_id == session_id)
    )
    notes = db.scalar(
        select(func.count()).select_from(BrewNote).where(BrewNote.brew_session_id == session_id)
    )
    attachments = db.scalar(
        select(func.count())
        .select_from(BrewAttachment)
        .where(BrewAttachment.brew_session_id == session_id)
    )
    journal = db.scalar(
        select(func.count())
        .select_from(BrewJournalEvent)
        .where(BrewJournalEvent.brew_session_id == session_id)
    )
    description = (
        f"{len(canonical)} canonical plan steps ({', '.join(canonical)}) plus "
        f"{repeats} repeated stage occurrences; {int(timers or 0)} timers; "
        f"{int(reminders or 0)} reminders; {int(measurements or 0)} measurements; "
        f"{int(additions or 0)} addition events; {int(notes or 0)} notes; "
        f"{int(attachments or 0)} attachment metadata rows; "
        f"{int(journal or 0)} BrewJournalEvents. Attachment bytes are not loaded "
        "by the dashboard projection."
    )
    return {
        "description": description,
        "canonical_stages": canonical,
        "canonical_stage_count": len(canonical),
        "repeated_occurrences": repeats,
        "timers": int(timers or 0),
        "reminders": int(reminders or 0),
        "measurements": int(measurements or 0),
        "additions": int(additions or 0),
        "notes": int(notes or 0),
        "attachment_metadata": int(attachments or 0),
        "journal_events": int(journal or 0),
        "stage_rows": len(stages),
    }


def _clone_repeated_occurrence(source: BrewStage, occurrence: int) -> BrewStage:
    return BrewStage(
        brew_session_id=source.brew_session_id,
        name=source.name,
        status="PENDING",
        target_duration_seconds=source.target_duration_seconds,
        target_temperature=source.target_temperature,
        temperature_unit=source.temperature_unit,
        target_ph=source.target_ph,
        ph_tolerance=source.ph_tolerance,
        target_gravity=source.target_gravity,
        gravity_tolerance=source.gravity_tolerance,
        plan_step_id=source.plan_step_id,
        canonical_stage_type=source.canonical_stage_type,
        occurrence_number=occurrence,
        required=source.required,
        runtime_occurrence_kind="REPEAT",
        runtime_source_stage_id=source.id,
        runtime_reason="Representative benchmark repeated occurrence",
    )


def create_isolated_benchmark_session(db: Session, user: User) -> BrewSession:
    """Create a disposable multi-stage Phase 3 session that is never a caller's live BrewSession."""
    now = utc_now()
    token = uuid.uuid4().hex[:12]
    recipe = Recipe(owner_id=user.id, name=f"bench-{token}")
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
        boil_duration_minutes=60,
        batch_size_liters=Decimal("20"),
        target_og=Decimal("1.052"),
        equipment_snapshot={"profile": "phase3-bench"},
        calculation_outputs={"total_liquor_liters": "28"},
    )
    db.add(version)
    db.flush()
    malt = Ingredient(
        owner_id=user.id,
        name=f"bench-malt-{token}",
        category="FERMENTABLE",
        canonical_unit="g",
    )
    hop = Ingredient(
        owner_id=user.id,
        name=f"bench-hop-{token}",
        category="HOP",
        canonical_unit="g",
    )
    db.add_all([malt, hop])
    db.flush()
    db.add_all(
        [
            RecipeProcessStep(
                recipe_version_id=version.id,
                step_type="MASH",
                sequence=1,
                name="Mash",
                duration_minutes=60,
                temperature_c=Decimal("66.7"),
                details={},
            ),
            RecipeProcessStep(
                recipe_version_id=version.id,
                step_type="BOIL",
                sequence=2,
                name="Boil",
                duration_minutes=60,
                details={},
            ),
            RecipeIngredient(
                recipe_version_id=version.id,
                ingredient_id=malt.id,
                amount=Decimal("5000.0000"),
                unit="g",
                use_stage="MASH",
                timing_minutes=0,
            ),
            RecipeIngredient(
                recipe_version_id=version.id,
                ingredient_id=hop.id,
                amount=Decimal("28.0000"),
                unit="g",
                use_stage="BOIL",
                timing_minutes=60,
            ),
            RecipeIngredient(
                recipe_version_id=version.id,
                ingredient_id=hop.id,
                amount=Decimal("14.0000"),
                unit="g",
                use_stage="WHIRLPOOL",
                timing_minutes=0,
            ),
        ]
    )
    db.flush()
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
        revision=1,
    )
    db.add(session)
    db.flush()
    stages = persist_plan(db, session, build_plan(db, version))
    by_type = {item.canonical_stage_type: item for item in stages}
    missing = [name for name in REQUIRED_THROUGH_PITCH if name not in by_type]
    if missing:
        raise RuntimeError(f"Benchmark plan is missing required stages: {missing}")
    session.status = "ACTIVE"
    session.started_at = now
    mash = by_type["MASH"]
    mash.status = "ACTIVE"
    mash.started_at = now
    for stage_type in ("MASH", "BOIL", "CHILL"):
        db.add(_clone_repeated_occurrence(by_type[stage_type], 2))
    db.flush()
    for index in range(REPRESENTATIVE_COUNTS["timers"]):
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
    for index in range(REPRESENTATIVE_COUNTS["reminders"]):
        db.add(
            Notification(
                brew_stage_id=mash.id,
                brew_session_id=session.id,
                notification_type=f"BENCH_REMINDER_{index:02d}",
                message=f"Benchmark reminder {index}",
                due_at=now,
                status="DUE" if index < 5 else "SCHEDULED",
                priority="REQUIRED" if index < 10 else "OPTIONAL",
            )
        )
    for index in range(REPRESENTATIVE_COUNTS["measurements"]):
        ph = index % 2 == 0
        db.add(
            Measurement(
                brew_stage_id=mash.id,
                brew_session_id=session.id,
                measurement_type="MASH_PH" if ph else "MASH_GRAVITY",
                value=Decimal("5.30") if ph else Decimal("1.050"),
                unit="pH" if ph else "SG",
                measured_at=now,
                provenance="BENCH",
                recorded_at=now,
                actor_user_id=user.id,
                process_point="MASH",
            )
        )
    boil = by_type["BOIL"]
    first_event: BrewAdditionEvent | None = None
    for index in range(REPRESENTATIVE_COUNTS["additions"]):
        requirement_id = uuid.uuid4()
        db.add(
            BrewStageRequirement(
                brew_session_id=session.id,
                stage_instance_id=boil.id,
                requirement_template_id=uuid.uuid4(),
                requirement_class="ADDITION",
                requirement_id=requirement_id,
                required=True,
                waivable=True,
                provenance="PLANNED",
                payload={
                    "definition_key": f"BENCH_ADDITION_{index:03d}",
                    "planned_amount": "10",
                    "planned_unit": "g",
                    "timing_basis": "UNSCHEDULED",
                    "source_addition_id": str(uuid.uuid4()),
                },
            )
        )
        event = BrewAdditionEvent(
            brew_session_id=session.id,
            stage_instance_id=boil.id,
            requirement_id=requirement_id,
            execution_status="EXECUTED",
            planned_amount=Decimal("10.0000"),
            planned_unit="g",
            actual_quantity=Decimal("10.0000"),
            actual_unit="g",
            actual_executed_at=now,
            recorded_at=now,
            actor_user_id=user.id,
            note=f"Benchmark hop charge {index}",
        )
        db.add(event)
        if first_event is None:
            first_event = event
    db.flush()
    if first_event is not None:
        db.add(
            BrewAdditionCorrection(
                brew_session_id=session.id,
                stage_instance_id=boil.id,
                original_addition_event_id=first_event.id,
                correction_of_id=first_event.id,
                execution_status="EXECUTED",
                actual_quantity=Decimal("11.0000"),
                actual_unit="g",
                changed_fields={"actual_quantity": "11.0000"},
                reason="Benchmark correction of hop charge",
                actor_user_id=user.id,
                recorded_at=now,
            )
        )
    for index in range(REPRESENTATIVE_COUNTS["notes"]):
        db.add(
            BrewNote(
                brew_session_id=session.id,
                stage_instance_id=mash.id,
                body=f"Benchmark note {index}",
                actor_user_id=user.id,
            )
        )
    for index in range(REPRESENTATIVE_COUNTS["attachment_metadata"]):
        db.add(
            BrewAttachment(
                brew_session_id=session.id,
                stage_instance_id=mash.id,
                storage_key=uuid.uuid4().hex,
                content_type="image/png",
                byte_length=67,
                sha256="0" * 64,
                original_filename=f"bench-{index:02d}.png",
                status="FINAL",
                actor_user_id=user.id,
            )
        )
    for index in range(_journal_event_target()):
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


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _ensure_schema(engine: Engine) -> None:
    from brewing_api.domain import model_registry  # noqa: F401
    from brewing_api.platform.database import Base

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        return
    with engine.connect() as connection:
        present = connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
        if present:
            return
    Base.metadata.create_all(engine)


def _isolated_benchmark_engine() -> tuple[Engine, dict, Callable[[], None]]:
    """Build a disposable engine. Never binds to a caller's live BrewSession."""
    url = os.environ.get("DATABASE_URL") or ""
    prefer_postgres = os.environ.get("TEST_USE_POSTGRES") == "1" or url.startswith("postgresql")
    env = {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "prefer_postgres": prefer_postgres,
    }
    if prefer_postgres and "postgresql" in url:
        try:
            from sqlalchemy.engine.url import make_url

            parsed = make_url(url)
            db_name = f"phase3_perf_{uuid.uuid4().hex[:10]}"
            admin = create_engine(
                parsed.set(database="postgres").render_as_string(hide_password=False),
                isolation_level="AUTOCOMMIT",
            )
            with admin.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{db_name}"'))
            target_url = parsed.set(database=db_name).render_as_string(hide_password=False)
            engine = create_engine(target_url, pool_pre_ping=True)
            _ensure_schema(engine)

            def cleanup() -> None:
                engine.dispose()
                try:
                    with admin.connect() as connection:
                        connection.execute(
                            text(
                                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                "WHERE datname = :name AND pid <> pg_backend_pid()"
                            ),
                            {"name": db_name},
                        )
                        connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
                finally:
                    admin.dispose()

            env.update(
                {
                    "engine": "postgresql-disposable",
                    "database": db_name,
                    "dialect": "postgresql",
                }
            )
            return engine, env, cleanup
        except Exception as exc:  # noqa: BLE001 - recorded fallback
            env["disposable_postgres_error"] = str(exc)
            try:
                engine = create_engine(url, pool_pre_ping=True)
                _ensure_schema(engine)
                env.update({"engine": "postgresql-shared-url", "dialect": "postgresql"})
                return engine, env, engine.dispose
            except Exception as shared_exc:  # noqa: BLE001
                env["shared_postgres_error"] = str(shared_exc)
    require_postgres = (
        os.environ.get("TEST_USE_POSTGRES") == "1"
        or os.environ.get("PHASE3_PERF_REQUIRE_POSTGRES") == "1"
    )
    if require_postgres:
        detail = (
            env.get("disposable_postgres_error")
            or env.get("shared_postgres_error")
            or "DATABASE_URL missing"
        )
        raise RuntimeError(
            "Phase 3 performance acceptance requires disposable/shared PostgreSQL; "
            f"unavailable ({detail})"
        )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _enable_sqlite_foreign_keys(engine)
    _ensure_schema(engine)
    env.update({"engine": "sqlite-memory", "dialect": "sqlite", "fallback": True})
    return engine, env, engine.dispose


def run_isolated_performance_harness(
    samples: int | None = None, warmup: int | None = None
) -> dict:
    engine, env_info, cleanup = _isolated_benchmark_engine()
    try:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with factory() as db:
            user = User(
                username=f"bench-{uuid.uuid4().hex[:10]}",
                password_hash="isolated-benchmark-hash",
            )
            db.add(user)
            db.commit()
            session = create_isolated_benchmark_session(db, user)
            dataset = describe_benchmark_dataset(db, session.id)
            report = run_performance_suite(
                db,
                user,
                session.id,
                samples=samples,
                warmup=warmup,
                dataset=dataset,
                environment=env_info,
            )
            artifact_dir = Path(
                os.environ.get(
                    "PHASE3_PERF_ARTIFACT_DIR",
                    str(Path(__file__).resolve().parents[5] / "docs" / "evidence"),
                )
            )
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_path = artifact_dir / "PHASE_3_PERFORMANCE_RAW_SAMPLES.json"
            artifact_path.write_text(
                json.dumps(
                    {
                        "generated_at": utc_now().isoformat(),
                        "environment": report.get("ENVIRONMENT"),
                        "dataset": report.get("dataset"),
                        "sample_count": report.get("SAMPLE_COUNT"),
                        "results": {
                            key: {
                                "status": value.get("status"),
                                "p50_ms": value.get("p50_ms"),
                                "p95_ms": value.get("p95_ms"),
                                "threshold_ms": value.get("threshold_ms"),
                                "raw_samples_ms": value.get("raw_samples_ms"),
                            }
                            for key, value in (report.get("results") or {}).items()
                        },
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            report["raw_sample_artifact"] = str(artifact_path)
            return report
    finally:
        cleanup()


def run_performance_suite(
    db: Session,
    user: User,
    session_id: uuid.UUID,
    samples: int | None = None,
    warmup: int | None = None,
    dataset: dict | None = None,
    environment: dict | None = None,
) -> dict:
    samples = samples if samples is not None else int(os.environ.get("PHASE3_PERF_SAMPLES", "100"))
    warmup = warmup if warmup is not None else int(os.environ.get("PHASE3_PERF_WARMUP", "10"))
    reset_metrics()
    stage = db.scalar(
        select(BrewStage).where(
            BrewStage.brew_session_id == session_id,
            BrewStage.canonical_stage_type == "MASH",
            BrewStage.occurrence_number == 1,
        )
    )
    assert stage is not None
    raw_samples: dict[str, list[float]] = {}

    def measure(name: str, fn) -> None:
        captured: list[float] = []
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
                    captured.append(record_duration(name, started, ok=ok))
        raw_samples[name] = captured

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
        current = db.get(BrewSession, session_id)
        assert current is not None
        phase3.acknowledge_reminder(
            db,
            user,
            target.id,
            expected_revision=current.revision,
            operation_id=f"bench-ack-{_i}-{uuid.uuid4().hex[:8]}",
        )

    if reminders:
        measure("reminder_ack", ack)

    journal_events = _journal_event_target()

    def journal_json(_i: int) -> None:
        events = brew_service.session_journal_events(db, user, session_id)
        assert len(events) >= journal_events
        payload = [
            {"id": str(item.id), "event_type": item.event_type, "message": item.message}
            for item in events
        ]
        assert len(payload) >= journal_events

    measure("journal_json_750", journal_json)

    def journal_html(_i: int) -> None:
        events = brew_service.session_journal_events(db, user, session_id)
        html = brew_service.render_journal_html(events)
        assert len(events) >= journal_events
        assert html.count("<li>") >= journal_events

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
            phase3.resume_session(
                db,
                user,
                session_id,
                current.revision,
                operation_id=f"bench-resume-{_i}-{uuid.uuid4().hex[:8]}",
            )

    measure("stage_transition", stage_transition)

    def measurement_plus(_i: int) -> None:
        brew_service.session_details(db, user, session_id)
        if reminders:
            target = reminders[0]
            if target.status != "ACKNOWLEDGED":
                current = db.get(BrewSession, session_id)
                assert current is not None
                phase3.acknowledge_reminder(
                    db,
                    user,
                    target.id,
                    expected_revision=current.revision,
                    operation_id=f"bench-meas-ack-{_i}-{uuid.uuid4().hex[:8]}",
                )

    measure("measurement_plus_reminder", measurement_plus)

    report = snapshot()
    results = {}
    for key, threshold in THRESHOLDS_MS.items():
        op = report["operations"].get(key)
        if op is None:
            results[key] = {
                "status": "SKIPPED",
                "RESULT": "SKIPPED",
                "threshold_ms": threshold,
                "THRESHOLD": threshold,
            }
            continue
        status = "PASS" if op["p95_ms"] <= threshold else "FAIL"
        results[key] = {
            "status": status,
            "RESULT": status,
            "count": op["count"],
            "SAMPLE_COUNT": op["count"],
            "p50_ms": round(op["p50_ms"], 3),
            "P50": round(op["p50_ms"], 3),
            "p95_ms": round(op["p95_ms"], 3),
            "P95": round(op["p95_ms"], 3),
            "threshold_ms": threshold,
            "THRESHOLD": threshold,
            "samples": op["count"],
            "raw_samples_ms": [round(value, 3) for value in raw_samples.get(key, [])],
        }
    failing = [name for name, item in results.items() if item["status"] != "PASS"]
    dataset = dataset or describe_benchmark_dataset(db, session_id)
    environment = environment or {}
    return {
        "rule_version": "phase3-performance-v1",
        "reference_class": "private-runtime-docker",
        "environment": os.environ.get("PHASE3_PERF_ENV")
        or environment.get("engine", "isolated-harness"),
        "ENVIRONMENT": {
            **environment,
            "PHASE3_PERF_ENV": os.environ.get("PHASE3_PERF_ENV", ""),
        },
        "DATASET": dataset["description"] if isinstance(dataset, dict) else str(dataset),
        "dataset": dataset,
        "SAMPLE_COUNT": samples,
        "sample_size": samples,
        "warmup": warmup,
        "method": "perf_counter p50/p95 over isolated disposable representative session",
        "results": results,
        "failing": failing,
        "all_pass": not failing,
        "isolated_session_id": str(session_id),
        "REAL_USER_SESSION_MUTATIONS": 0,
        "production_route": "ABSENT",
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
