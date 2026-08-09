from fastapi import APIRouter

from app.api.v1 import brewery, calculations, equipment, ingredients, inventory, meta, recipes

api_router = APIRouter()
api_router.include_router(meta.router, tags=["meta"])
api_router.include_router(brewery.router)
api_router.include_router(equipment.router)
api_router.include_router(ingredients.router)
api_router.include_router(inventory.router)
api_router.include_router(recipes.router)
api_router.include_router(calculations.router)
