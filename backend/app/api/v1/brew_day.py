from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrewEvent
from app.db.session import get_db
from app.schemas.brew_day import (
    BrewEventRead,
    BrewPlanCreate,
    BrewPlanRead,
    BrewSessionCreate,
    BrewSessionRead,
    InstrumentCorrectionRequest,
    MeasurementCaptureRequest,
    MeasurementMissRequest,
    MeasurementRevisionRequest,
    MeasurementWaiveRequest,
    SessionTransitionRequest,
)
from app.services import brew_plan as brew_plan_service
from app.services import brew_session as brew_session_service
from app.services import brew_transitions as brew_transitions_service
from app.services import measurements as measurement_service

router = APIRouter(tags=["brew-day"])


@router.post(
    "/recipe-versions/{version_id}/brew-plans",
    response_model=BrewPlanRead,
    status_code=201,
)
async def create_brew_plan(
    version_id: str,
    payload: BrewPlanCreate,
    db: AsyncSession = Depends(get_db),
):
    return await brew_plan_service.create_brew_plan(db, version_id, payload)


@router.post(
    "/brew-plans/{plan_id}/sessions",
    response_model=BrewSessionRead,
    status_code=201,
)
async def create_brew_session(
    plan_id: str,
    payload: BrewSessionCreate,
    db: AsyncSession = Depends(get_db),
):
    return await brew_session_service.create_brew_session(db, plan_id, payload)


@router.get("/brew-sessions/{session_id}", response_model=BrewSessionRead)
async def get_brew_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Side-effect free BrewSession read."""
    return await brew_session_service.get_brew_session_read(db, session_id)


@router.post(
    "/brew-sessions/{session_id}/transitions",
    response_model=BrewSessionRead,
)
async def apply_session_transition(
    session_id: str,
    payload: SessionTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    return await brew_transitions_service.apply_transition(db, session_id, payload)


@router.get("/brew-sessions/{session_id}/events")
async def list_session_events(session_id: str, db: AsyncSession = Depends(get_db)):
    """Append-only BrewEvent timeline for a session (side-effect free)."""
    await brew_session_service.get_brew_session(db, session_id)
    result = await db.execute(
        select(BrewEvent)
        .where(BrewEvent.brew_session_id == session_id)
        .order_by(BrewEvent.occurred_at.asc(), BrewEvent.id.asc())
    )
    return [BrewEventRead.model_validate(e) for e in result.scalars().all()]


@router.get("/brew-sessions/{session_id}/requirements")
async def list_requirements(session_id: str, db: AsyncSession = Depends(get_db)):
    return await measurement_service.list_session_requirements(db, session_id)


@router.post("/brew-sessions/{session_id}/measurements", status_code=201)
async def capture_measurement(
    session_id: str,
    payload: MeasurementCaptureRequest,
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.capture_measurement(db, session_id, payload)


@router.post("/measurement-records/{record_id}/instrument-corrections")
async def instrument_correction(
    record_id: str,
    payload: InstrumentCorrectionRequest,
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.instrument_correction(db, record_id, payload)


@router.post("/measurement-records/{record_id}/revisions")
async def user_revision(
    record_id: str,
    payload: MeasurementRevisionRequest,
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.user_revision(db, record_id, payload)


@router.post("/measurement-requirements/{requirement_id}/miss")
async def miss_requirement(
    requirement_id: str,
    payload: MeasurementMissRequest,
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.miss_requirement(db, requirement_id, payload)


@router.post("/measurement-requirements/{requirement_id}/waive")
async def waive_requirement(
    requirement_id: str,
    payload: MeasurementWaiveRequest,
    db: AsyncSession = Depends(get_db),
):
    return await measurement_service.waive_requirement(db, requirement_id, payload)


@router.get("/measurement-requirements/{requirement_id}/observation-history")
async def observation_history(requirement_id: str, db: AsyncSession = Depends(get_db)):
    return await measurement_service.list_observation_history(db, requirement_id)


@router.get("/measurement-requirements/{requirement_id}/status-history")
async def status_history(requirement_id: str, db: AsyncSession = Depends(get_db)):
    return await measurement_service.list_status_history(db, requirement_id)
