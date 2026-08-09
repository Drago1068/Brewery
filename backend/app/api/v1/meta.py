from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppMeta
from app.db.session import get_db

router = APIRouter()


@router.get("/meta")
async def get_meta(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppMeta).where(AppMeta.key == "epic"))
    epic_row = result.scalar_one_or_none()

    return {
        "name": "BrewingOS",
        "product": "Brewing Intelligence & Competition OS",
        "version": "0.1.0",
        "epic": int(epic_row.value) if epic_row else 1,
        "increment": 5,
        "environment": settings.brewingos_env,
        "modules": {
            "infrastructure": "active",
            "brewery": "active",
            "equipment": "active",
            "ingredients": "active",
            "inventory": "active",
            "recipes": "active",
            "calculations": "active",
            "readiness": "planned",
        },
        "persistence": {
            "database": "postgresql",
            "storage_path": settings.storage_path,
            "log_path": settings.log_path,
        },
    }
