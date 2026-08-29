"""Concurrent PostgreSQL client proofs for repeat / controlled-return (P3-IMPL-RR-003)."""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_phase3_adversarial import _record

from brewing_api.application.errors import ConflictError, DomainError
from brewing_api.application.phase3.commands import repeat_or_return_stage
from brewing_api.domain.brew_day.models import BrewStageRequirement
from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage
from brewing_api.domain.identity.models import User
from brewing_api.platform.database import SessionLocal
from brewing_api.platform.time import utc_now

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("TEST_USE_POSTGRES") != "1",
        reason="Concurrent repeat/return proof requires PostgreSQL (TEST_USE_POSTGRES=1)",
    ),
]

_REPEAT_REASON = "Need another rest after iodine failed"
_RETURN_REASON = "Return to mash after later stage completed"


def _complete_mash(active_mash: dict) -> None:
    client = active_mash["client"]
    stage_id = active_mash["stage_id"]
    command = active_mash["command"]
    assert _record(client, stage_id, "MASH_PH", "5.30", "pH").status_code == 201
    assert _record(client, stage_id, "MASH_GRAVITY", "1.050", "SG").status_code == 201
    completed = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/complete",
        json=command(),
    )
    assert completed.status_code == 200, completed.text


def _reopen_session_for_runtime_occurrence(session_id: str, *, reset_later_stages: bool) -> None:
    """Legacy mash completion also completes the session; reopen so repeat/return can run."""
    with SessionLocal() as db:
        session = db.get(BrewSession, uuid.UUID(session_id))
        assert session is not None
        session.status = "ACTIVE"
        session.completed_at = None
        if reset_later_stages:
            for stage in db.scalars(
                select(BrewStage).where(BrewStage.brew_session_id == session.id)
            ).all():
                if (stage.canonical_stage_type or stage.name) == "BREW_COMPLETE":
                    stage.status = "PENDING"
                    stage.completed_at = None
        db.commit()


def _mash_occurrences(session_id: uuid.UUID, plan_step_id: uuid.UUID | None) -> list[BrewStage]:
    with SessionLocal() as db:
        stages = list(
            db.scalars(select(BrewStage).where(BrewStage.brew_session_id == session_id)).all()
        )
    return [
        item
        for item in stages
        if item.plan_step_id == plan_step_id
        or (plan_step_id is None and (item.canonical_stage_type or item.name) == "MASH")
    ]


def _race_repeat_or_return(
    *,
    user_id: uuid.UUID,
    source_stage_id: uuid.UUID,
    kind: str,
    reason: str,
    expected_revision: int,
    operation_ids: tuple[str, str],
) -> list[tuple[str, object]]:
    barrier = threading.Barrier(2, timeout=10)

    def worker(operation_id: str) -> tuple[str, object]:
        try:
            with SessionLocal() as db:
                user = db.get(User, user_id)
                assert user is not None
                barrier.wait()
                stage = repeat_or_return_stage(
                    db,
                    user,
                    source_stage_id,
                    kind,
                    reason,
                    expected_revision,
                    operation_id,
                )
                return ("ok", stage)
        except ConflictError as exc:
            return ("conflict", exc)
        except IntegrityError as exc:
            return ("conflict", exc)
        except DomainError as exc:
            return ("error", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, operation_id) for operation_id in operation_ids]
        return [future.result(timeout=30) for future in futures]


def test_concurrent_repeat_one_winner_no_duplicate_occurrences(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    _complete_mash(active_mash)
    _reopen_session_for_runtime_occurrence(session_id, reset_later_stages=True)

    with SessionLocal() as db:
        session = db.get(BrewSession, uuid.UUID(session_id))
        source = db.get(BrewStage, uuid.UUID(stage_id))
        assert session is not None and source is not None
        user_id = session.user_id
        revision = session.revision
        plan_step_id = source.plan_step_id
        source_id = source.id

    results = _race_repeat_or_return(
        user_id=user_id,
        source_stage_id=source_id,
        kind="REPEAT",
        reason=_REPEAT_REASON,
        expected_revision=revision,
        operation_ids=("repeat-race-a", "repeat-race-b"),
    )
    outcomes = [item[0] for item in results]
    assert outcomes.count("ok") == 1, results
    assert outcomes.count("conflict") == 1, results
    assert "error" not in outcomes, results

    winner = next(item[1] for item in results if item[0] == "ok")
    assert winner.id != source_id
    assert winner.occurrence_number == 2
    assert winner.runtime_occurrence_kind == "REPEAT"
    assert winner.status == "ACTIVE"

    mash_rows = _mash_occurrences(uuid.UUID(session_id), plan_step_id)
    occurrence_numbers = [item.occurrence_number for item in mash_rows]
    assert len(occurrence_numbers) == len(set(occurrence_numbers))
    assert sorted(occurrence_numbers) == [1, 2]
    assert sum(1 for item in mash_rows if item.status == "ACTIVE") == 1

    with SessionLocal() as db:
        requirements = list(
            db.scalars(
                select(BrewStageRequirement).where(
                    BrewStageRequirement.stage_instance_id == winner.id
                )
            ).all()
        )
    assert requirements
    assert all(item.provenance == "RUNTIME_REPEAT_RULE" for item in requirements)
    assert any(item.requirement_class == "MEASUREMENT" for item in requirements)
    details = client.get(f"/api/v1/brew-sessions/{session_id}").json()
    assert details["status"] == "ACTIVE"


def test_concurrent_repeat_same_operation_replays(active_mash):
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    _complete_mash(active_mash)
    _reopen_session_for_runtime_occurrence(session_id, reset_later_stages=True)

    with SessionLocal() as db:
        session = db.get(BrewSession, uuid.UUID(session_id))
        source = db.get(BrewStage, uuid.UUID(stage_id))
        assert session is not None and source is not None
        user_id = session.user_id
        revision = session.revision
        plan_step_id = source.plan_step_id
        source_id = source.id

    results = _race_repeat_or_return(
        user_id=user_id,
        source_stage_id=source_id,
        kind="REPEAT",
        reason=_REPEAT_REASON,
        expected_revision=revision,
        operation_ids=("repeat-replay-1", "repeat-replay-1"),
    )
    assert all(item[0] == "ok" for item in results), results
    ids = {item[1].id for item in results}
    assert len(ids) == 1
    winner_id = next(iter(ids))
    assert winner_id != source_id

    mash_rows = _mash_occurrences(uuid.UUID(session_id), plan_step_id)
    occurrence_numbers = [item.occurrence_number for item in mash_rows]
    assert sorted(occurrence_numbers) == [1, 2]
    assert len(occurrence_numbers) == len(set(occurrence_numbers))


def test_concurrent_controlled_return_one_winner_no_duplicate_occurrences(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    command = active_mash["command"]
    _complete_mash(active_mash)
    _reopen_session_for_runtime_occurrence(session_id, reset_later_stages=True)

    repeated = client.post(
        f"/api/v1/brew-sessions/stages/{stage_id}/repeat",
        json=command(reason=_REPEAT_REASON, operation_id="return-setup-repeat"),
    )
    assert repeated.status_code == 200, repeated.text
    repeated_id = uuid.UUID(repeated.json()["id"])

    with SessionLocal() as db:
        later = db.get(BrewStage, repeated_id)
        assert later is not None
        later.status = "COMPLETED"
        later.completed_at = utc_now()
        db.commit()
        session = db.get(BrewSession, uuid.UUID(session_id))
        source = db.get(BrewStage, uuid.UUID(stage_id))
        assert session is not None and source is not None
        user_id = session.user_id
        revision = session.revision
        plan_step_id = source.plan_step_id
        source_id = source.id

    results = _race_repeat_or_return(
        user_id=user_id,
        source_stage_id=source_id,
        kind="RETURN",
        reason=_RETURN_REASON,
        expected_revision=revision,
        operation_ids=("return-race-a", "return-race-b"),
    )
    outcomes = [item[0] for item in results]
    assert outcomes.count("ok") == 1, results
    assert outcomes.count("conflict") == 1, results

    winner = next(item[1] for item in results if item[0] == "ok")
    assert winner.runtime_occurrence_kind == "RETURN"
    assert winner.occurrence_number == 3
    assert winner.status == "ACTIVE"

    mash_rows = _mash_occurrences(uuid.UUID(session_id), plan_step_id)
    occurrence_numbers = [item.occurrence_number for item in mash_rows]
    assert len(occurrence_numbers) == len(set(occurrence_numbers))
    assert sorted(occurrence_numbers) == [1, 2, 3]

    with SessionLocal() as db:
        requirements = list(
            db.scalars(
                select(BrewStageRequirement).where(
                    BrewStageRequirement.stage_instance_id == winner.id
                )
            ).all()
        )
    assert requirements
    assert all(item.provenance == "CONTROLLED_RETURN_RULE" for item in requirements)
    assert any(item.requirement_class == "MEASUREMENT" for item in requirements)


def test_concurrent_http_repeat_one_winner_no_duplicate_occurrences(active_mash):
    client = active_mash["client"]
    session_id = active_mash["session_id"]
    stage_id = active_mash["stage_id"]
    _complete_mash(active_mash)
    _reopen_session_for_runtime_occurrence(session_id, reset_later_stages=True)
    revision = client.get(f"/api/v1/brew-sessions/{session_id}").json()["revision"]
    barrier = threading.Barrier(2, timeout=10)
    path = f"/api/v1/brew-sessions/stages/{stage_id}/repeat"

    def post(operation_id: str):
        barrier.wait()
        return client.post(
            path,
            json={
                "operation_id": operation_id,
                "expected_revision": revision,
                "reason": _REPEAT_REASON,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = [
            future.result(timeout=30)
            for future in (
                pool.submit(post, "http-repeat-a"),
                pool.submit(post, "http-repeat-b"),
            )
        ]
    statuses = sorted(item.status_code for item in responses)
    assert 200 in statuses, [item.text for item in responses]
    assert statuses == [200, 409], [item.text for item in responses]
    winner = next(item for item in responses if item.status_code == 200)
    loser = next(item for item in responses if item.status_code == 409)
    assert winner.json()["id"] != stage_id
    assert loser.status_code == 409

    with SessionLocal() as db:
        source = db.get(BrewStage, uuid.UUID(stage_id))
        assert source is not None
        mash_rows = _mash_occurrences(uuid.UUID(session_id), source.plan_step_id)
        winner_row = db.get(BrewStage, uuid.UUID(winner.json()["id"]))
        assert winner_row is not None
        requirements = list(
            db.scalars(
                select(BrewStageRequirement).where(
                    BrewStageRequirement.stage_instance_id == winner_row.id
                )
            ).all()
        )
    occurrence_numbers = [item.occurrence_number for item in mash_rows]
    assert sorted(occurrence_numbers) == [1, 2]
    assert len(occurrence_numbers) == len(set(occurrence_numbers))
    assert requirements
    assert all(item.provenance == "RUNTIME_REPEAT_RULE" for item in requirements)
