import uuid

from fastapi import APIRouter, status

from brewing_api.application import brew_day as service
from brewing_api.presentation.dependencies import CurrentUser, Db
from brewing_api.presentation.schemas import BrewSessionCreate, IdStatusResponse, MeasurementCreate

router = APIRouter(prefix="/brew-sessions", tags=["brew-day"])


def _decimal(value: object | None) -> str | None:
    return None if value is None else str(value)


def serialize_details(details: dict) -> dict:
    session = details["session"]
    version = details["version"]
    stage = details["stage"]
    timer = details["timer"]
    deviations = {item.measurement_id: item for item in details["deviations"]}
    return {
        "id": str(session.id),
        "status": session.status,
        "started_at": session.started_at,
        "completed_at": session.completed_at,
        "recipe_version": {
            "id": str(version.id),
            "version_number": version.version_number,
        },
        "planned": {
            "mash_temperature": _decimal(session.target_mash_temperature),
            "temperature_unit": session.mash_temperature_unit,
            "mash_ph": _decimal(session.target_mash_ph),
            "mash_ph_tolerance": _decimal(session.mash_ph_tolerance),
            "mash_gravity": _decimal(session.target_mash_gravity),
            "mash_gravity_tolerance": _decimal(session.mash_gravity_tolerance),
            "mash_duration_minutes": session.planned_mash_duration_minutes,
        },
        "mash": None
        if stage is None
        else {
            "id": str(stage.id),
            "status": stage.status,
            "started_at": stage.started_at,
            "completed_at": stage.completed_at,
            "timer": None
            if timer is None
            else {
                "id": str(timer.id),
                "status": timer.status,
                "started_at": timer.started_at,
                "planned_duration_seconds": timer.planned_duration_seconds,
                "elapsed_seconds": details["timer_elapsed_seconds"],
                "completed_at": timer.completed_at,
            },
            "measurements": [
                {
                    "id": str(item.id),
                    "type": item.measurement_type,
                    "value": _decimal(item.value),
                    "unit": item.unit,
                    "measured_at": item.measured_at,
                    "note": item.note,
                    "instrument": item.instrument,
                    "provenance": item.provenance,
                    "correction_of_id": (
                        str(item.correction_of_id) if item.correction_of_id else None
                    ),
                    "deviation": None
                    if item.id not in deviations
                    else {
                        "variance": _decimal(deviations[item.id].variance),
                        "tolerance": _decimal(deviations[item.id].tolerance),
                        "status": deviations[item.id].status,
                    },
                }
                for item in details["measurements"]
            ],
            "notifications": [
                {
                    "id": str(item.id),
                    "type": item.notification_type,
                    "message": item.message,
                    "status": item.status,
                    "due_at": item.due_at,
                }
                for item in details["notifications"]
            ],
        },
        "journal": [
            {
                "id": str(item.id),
                "event_type": item.event_type,
                "message": item.message,
                "created_at": item.created_at,
                "data": item.event_data,
            }
            for item in details["journal"]
        ],
    }


@router.post("", response_model=IdStatusResponse, status_code=status.HTTP_201_CREATED)
def create_session(command: BrewSessionCreate, db: Db, user: CurrentUser) -> IdStatusResponse:
    session = service.start_session(db, user, command.recipe_version_id)
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/start", response_model=IdStatusResponse)
def start_session(session_id: uuid.UUID, db: Db, user: CurrentUser) -> IdStatusResponse:
    session = service.activate_session(db, user, session_id)
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/mash/start", response_model=IdStatusResponse)
def start_mash(session_id: uuid.UUID, db: Db, user: CurrentUser) -> IdStatusResponse:
    stage = service.start_mash(db, user, session_id)
    return IdStatusResponse(id=stage.id, status=stage.status)


@router.get("/active")
def active(db: Db, user: CurrentUser) -> dict | None:
    session = service.active_session(db, user)
    return (
        None
        if session is None
        else serialize_details(service.session_details(db, user, session.id))
    )


@router.get("/{session_id}")
def details(session_id: uuid.UUID, db: Db, user: CurrentUser) -> dict:
    return serialize_details(service.session_details(db, user, session_id))


@router.post("/stages/{stage_id}/measurements", status_code=status.HTTP_201_CREATED)
def measurement(stage_id: uuid.UUID, command: MeasurementCreate, db: Db, user: CurrentUser) -> dict:
    item, deviation = service.record_measurement(db, user, stage_id, command)
    return {
        "id": str(item.id),
        "type": item.measurement_type,
        "value": str(item.value),
        "unit": item.unit,
        "deviation_created": deviation is not None,
    }


@router.post("/measurements/{measurement_id}/corrections", status_code=status.HTTP_201_CREATED)
def correction(
    measurement_id: uuid.UUID, command: MeasurementCreate, db: Db, user: CurrentUser
) -> dict:
    item = service.correct_measurement(db, user, measurement_id, command)
    return {"id": str(item.id), "correction_of_id": str(item.correction_of_id)}


@router.post("/stages/{stage_id}/complete", response_model=IdStatusResponse)
def complete(stage_id: uuid.UUID, db: Db, user: CurrentUser) -> IdStatusResponse:
    stage = service.complete_mash(db, user, stage_id)
    return IdStatusResponse(id=stage.id, status=stage.status)
