from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.brew_day import BrewPlanCreate, BrewPlanRead, BrewSessionCreate, BrewSessionRead
from app.services import brew_plan as brew_plan_service
from app.services import brew_session as brew_session_service

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
