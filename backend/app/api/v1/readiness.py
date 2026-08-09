from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import readiness as readiness_service

router = APIRouter(tags=["readiness"])


@router.post("/recipe-versions/{version_id}/readiness")
async def evaluate_readiness(version_id: str, db: AsyncSession = Depends(get_db)):
    """Evaluate Ready-to-Brew status. Side-effect free — does not consume inventory."""
    return await readiness_service.evaluate_recipe_version(db, version_id)
