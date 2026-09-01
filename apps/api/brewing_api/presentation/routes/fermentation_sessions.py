import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from brewing_api.application.phase4 import commands, read_models
from brewing_api.presentation.dependencies import CurrentUser, Db

router = APIRouter(prefix="/fermentation-sessions", tags=["fermentation"])


class StartFermentationCommand(BaseModel):
    operation_id: str = Field(min_length=1, max_length=64)
    expected_brew_revision: int | None = Field(default=None, ge=0)


@router.post(
    "/brew-sessions/{brew_session_id}/start",
    status_code=status.HTTP_201_CREATED,
)
def start_fermentation_session(
    brew_session_id: uuid.UUID,
    body: StartFermentationCommand,
    user: CurrentUser,
    db: Db,
) -> dict:
    session = commands.start_fermentation_session(
        db,
        user,
        brew_session_id,
        operation_id=body.operation_id,
        expected_brew_revision=body.expected_brew_revision,
    )
    return read_models.serialize_session(db, user, session.id)


@router.get("/{fermentation_session_id}")
def get_fermentation_session(
    fermentation_session_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
) -> dict:
    return read_models.serialize_session(db, user, fermentation_session_id)
