import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from brewing_api.application import brew_day as service
from brewing_api.application.phase3 import additions as addition_service
from brewing_api.application.phase3 import commands as phase3
from brewing_api.application.phase3 import media as media_service
from brewing_api.application.phase3 import timers as timer_service
from brewing_api.application.phase3 import waivers as waiver_service
from brewing_api.application.phase3.plan import build_plan, declarations_from_payload
from brewing_api.application.phase3.voice import parse_voice_proposal
from brewing_api.application.recipes import get_owned_version
from brewing_api.presentation.dependencies import CurrentUser, Db
from brewing_api.presentation.schemas import BrewSessionCreate, IdStatusResponse, MeasurementCreate

router = APIRouter(prefix="/brew-sessions", tags=["brew-day"])
preview_router = APIRouter(tags=["brew-day"])


class SessionCommand(BaseModel):
    operation_id: str = Field(min_length=1, max_length=64)
    expected_revision: int | None = None
    reason: str | None = None
    name: str | None = None
    extra_seconds: int | None = None
    body: str | None = None
    yeast_addition_note: str | None = None
    pitch_temperature_c: str | None = None
    quantity: str | None = None
    unit: str | None = None
    execution_status: str | None = None
    correction_of_id: uuid.UUID | None = None
    planned_duration_seconds: int | None = None
    transcript: str | None = None
    caption: str | None = None


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
                    "process_point": item.process_point,
                    "method": item.method,
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
        "plan_kind": session.plan_kind,
        "revision": session.revision,
        "logical_plan_hash": session.logical_plan_hash,
        "stages": [
            {
                "id": str(item.id),
                "name": item.name,
                "canonical_stage_type": item.canonical_stage_type,
                "status": item.status,
                "occurrence_number": item.occurrence_number,
                "plan_step_id": str(item.plan_step_id) if item.plan_step_id else None,
                "required": item.required,
                "runtime_occurrence_kind": item.runtime_occurrence_kind,
            }
            for item in details.get("stages", [])
        ],
        "current_stage": None
        if not details.get("current_stage")
        else {
            "id": str(details["current_stage"].id),
            "name": details["current_stage"].name,
            "status": details["current_stage"].status,
            "canonical_stage_type": details["current_stage"].canonical_stage_type,
        },
        "timers": [
            {
                "id": str(item.id),
                "name": item.name,
                "status": item.status,
                "started_at": item.started_at,
                "planned_duration_seconds": item.planned_duration_seconds,
                "elapsed_seconds": service.timer_elapsed_seconds(item),
                "deadline_at": item.deadline_at,
                "clock_basis": item.clock_basis,
                "timer_type": item.timer_type,
                "brew_stage_id": str(item.brew_stage_id),
                "paused_at": item.paused_at,
            }
            for item in details.get("timers", [])
        ],
        "notes": [
            {"id": str(item.id), "body": item.body, "created_at": item.created_at}
            for item in details.get("notes", [])
        ],
        "waivers": [
            {
                "id": str(item.id),
                "status": item.status,
                "reason": item.reason,
                "requirement_id": str(item.requirement_id),
            }
            for item in details.get("waivers", [])
        ],
        "requirements": [
            {
                "id": str(item.requirement_id),
                "class": item.requirement_class,
                "status": item.status,
                "required": item.required,
                "waivable": item.waivable,
                "stage_instance_id": str(item.stage_instance_id),
                "definition_key": (item.payload or {}).get("definition_key"),
                "planned_amount": (item.payload or {}).get("planned_amount"),
                "planned_unit": (item.payload or {}).get("planned_unit"),
                "timing_basis": (item.payload or {}).get("timing_basis"),
                "source_addition_id": (item.payload or {}).get("source_addition_id"),
            }
            for item in details.get("requirements", [])
        ],
        "additions": [
            {
                "id": str(item.id),
                "status": item.execution_status,
                "planned_amount": _decimal(item.planned_amount),
                "planned_unit": item.planned_unit,
                "actual_quantity": _decimal(item.actual_quantity),
                "actual_unit": item.actual_unit,
                "requirement_id": str(item.requirement_id),
                "stage_instance_id": str(item.stage_instance_id),
            }
            for item in details.get("additions", [])
        ],
        "attachments": [
            {
                "id": str(item.id),
                "status": item.status,
                "content_type": item.content_type,
                "caption": item.caption,
                "unavailable": False,
            }
            for item in details.get("attachments", [])
            if item.removed_at is None
        ],
        "next_required_action": details.get("next_required_action"),
        "due_reminders": [
            {
                "id": str(item.id),
                "type": item.notification_type,
                "message": item.message,
                "status": item.status,
                "due_at": item.due_at,
            }
            for item in details.get("all_notifications", [])
            if item.status in {"DUE", "EXPIRED", "ACKNOWLEDGED"}
        ],
    }


@router.post("", response_model=IdStatusResponse, status_code=status.HTTP_201_CREATED)
def create_session(command: BrewSessionCreate, db: Db, user: CurrentUser) -> IdStatusResponse:
    session = service.start_session(
        db,
        user,
        command.recipe_version_id,
        declarations_from_payload(command.addition_repeat_declarations),
        command.plan_preview_hash,
    )
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/start", response_model=IdStatusResponse)
def start_session(
    session_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    session = service.activate_session(db, user, session_id)
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/ready", response_model=IdStatusResponse)
def ready_session(session_id: uuid.UUID, db: Db, user: CurrentUser) -> IdStatusResponse:
    session = service.mark_ready(db, user, session_id)
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/complete", response_model=IdStatusResponse)
def complete_session(session_id: uuid.UUID, db: Db, user: CurrentUser) -> IdStatusResponse:
    session = service.complete_session(db, user, session_id)
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/mash/start", response_model=IdStatusResponse)
def start_mash(
    session_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
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
def complete(
    stage_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    stage = phase3.complete_stage(db, user, stage_id)
    return IdStatusResponse(id=stage.id, status=stage.status)


@preview_router.get("/recipe-versions/{version_id}/phase3-plan-preview")
def plan_preview(version_id: uuid.UUID, db: Db, user: CurrentUser) -> dict:
    version = get_owned_version(db, user, version_id)
    plan = build_plan(db, version)
    return {
        "plan_preview_hash": plan.preview_hash,
        "plan_kind": plan.plan_kind,
        "logical_plan_hash": plan.logical_plan_hash,
        "steps": [
            {
                "plan_step_id": str(step.plan_step_id),
                "canonical_stage_type": step.canonical_stage_type,
                "required": step.required,
                "source_kind": step.source_kind,
                "source_process_step_id": str(step.source_process_step_id)
                if step.source_process_step_id
                else None,
                "occurrence": step.planned_same_type_ordinal,
                "additions": step.additions,
            }
            for step in plan.steps
        ],
        "addition_assignments": list(plan.addition_assignments),
    }


@router.post("/{session_id}/pause", response_model=IdStatusResponse)
def pause(
    session_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    session = phase3.pause_session(
        db,
        user,
        session_id,
        command.expected_revision if command else None,
        command.operation_id if command else None,
    )
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/resume", response_model=IdStatusResponse)
def resume(
    session_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    session = phase3.resume_session(
        db, user, session_id, (command.expected_revision if command else None)
    )
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/abort", response_model=IdStatusResponse)
def abort(
    session_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    session = phase3.abort_session(
        db, user, session_id, command.reason or "", command.expected_revision
    )
    return IdStatusResponse(id=session.id, status=session.status)


@router.post("/{session_id}/notes", status_code=status.HTTP_201_CREATED)
def add_note(session_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser) -> dict:
    note = phase3.create_note(db, user, session_id, command.body or "")
    return {"id": str(note.id)}


@router.post("/stages/{stage_instance_id}/start", response_model=IdStatusResponse)
def start_stage(
    stage_instance_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    stage = phase3.start_stage(
        db, user, stage_instance_id, command.expected_revision if command else None
    )
    return IdStatusResponse(id=stage.id, status=stage.status)


@router.post("/stages/{stage_instance_id}/skip", response_model=IdStatusResponse)
def skip_stage(
    stage_instance_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    stage = phase3.skip_stage(
        db, user, stage_instance_id, command.reason or "", command.expected_revision
    )
    return IdStatusResponse(id=stage.id, status=stage.status)


@router.post("/stages/{stage_instance_id}/extend", response_model=IdStatusResponse)
def extend_stage(
    stage_instance_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    stage = phase3.extend_stage(
        db,
        user,
        stage_instance_id,
        command.extra_seconds or 0,
        command.reason or "timer extension",
        command.operation_id,
    )
    return IdStatusResponse(id=stage.id, status=stage.status)


@router.post("/stages/{stage_instance_id}/timers", status_code=status.HTTP_201_CREATED)
def start_auxiliary_timer(
    stage_instance_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    timer = timer_service.start_auxiliary_timer(
        db,
        user,
        stage_instance_id,
        command.name or command.body or "Auxiliary timer",
        command.planned_duration_seconds or 300,
        command.operation_id,
        command.expected_revision,
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/stages/{stage_instance_id}/repeat", response_model=IdStatusResponse)
def repeat_stage(
    stage_instance_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    stage = phase3.repeat_or_return_stage(
        db,
        user,
        stage_instance_id,
        "REPEAT",
        command.reason or "",
        command.expected_revision,
        command.operation_id,
    )
    return IdStatusResponse(id=stage.id, status=stage.status)


@router.post("/stages/{stage_instance_id}/return", response_model=IdStatusResponse)
def return_stage(
    stage_instance_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    stage = phase3.repeat_or_return_stage(
        db,
        user,
        stage_instance_id,
        "RETURN",
        command.reason or "",
        command.expected_revision,
        command.operation_id,
    )
    return IdStatusResponse(id=stage.id, status=stage.status)


@router.post("/reminders/{reminder_id}/acknowledge", response_model=IdStatusResponse)
def ack_reminder(
    reminder_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    reminder = phase3.acknowledge_reminder(db, user, reminder_id)
    return IdStatusResponse(id=reminder.id, status=reminder.status)


@router.get("/{session_id}/journal")
def journal_view(session_id: uuid.UUID, db: Db, user: CurrentUser) -> dict:
    details = service.session_details(db, user, session_id)
    return {"events": serialize_details(details)["journal"]}


@router.get("/{session_id}/completion-audit")
def audit_view(session_id: uuid.UUID, db: Db, user: CurrentUser) -> dict:
    return phase3.completion_audit(db, user, session_id)


@router.get("/{session_id}/export")
def export_session(session_id: uuid.UUID, db: Db, user: CurrentUser, format: str = "json") -> dict:
    details = serialize_details(service.session_details(db, user, session_id))
    if format == "html":
        rows = "".join(
            f"<li>{item['created_at']}: {item['message']}</li>" for item in details["journal"]
        )
        return {
            "format": "html",
            "html": f"<html><body><h1>Brew journal</h1><ol>{rows}</ol></body></html>",
        }
    return {"format": "json", "document": details}


@router.post("/{session_id}/pitch-handoff", status_code=status.HTTP_201_CREATED)
def pitch(session_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser) -> dict:
    handoff = phase3.record_pitch_handoff(db, user, session_id, command.yeast_addition_note or "")
    return {"id": str(handoff.id), "pitched_at": handoff.pitched_at}


@router.post("/{session_id}/requirements/{requirement_id}/additions", status_code=201)
def execute_addition(
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    command: SessionCommand,
    db: Db,
    user: CurrentUser,
) -> dict:
    from decimal import Decimal

    event = addition_service.execute_addition(
        db,
        user,
        session_id,
        requirement_id,
        Decimal(command.quantity or "0"),
        command.unit or "g",
        command.operation_id,
        command.body,
    )
    return {"id": str(event.id), "status": event.execution_status}


@router.post("/{session_id}/requirements/{requirement_id}/additions/skip", status_code=201)
def skip_addition(
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    command: SessionCommand,
    db: Db,
    user: CurrentUser,
) -> dict:
    event = addition_service.skip_addition(
        db, user, session_id, requirement_id, command.reason or "", command.operation_id
    )
    return {"id": str(event.id), "status": event.execution_status}


@router.post("/{session_id}/addition-events/{addition_event_id}/corrections", status_code=201)
def correct_addition(
    session_id: uuid.UUID,
    addition_event_id: uuid.UUID,
    command: SessionCommand,
    db: Db,
    user: CurrentUser,
) -> dict:
    from decimal import Decimal

    correction = addition_service.correct_addition(
        db,
        user,
        session_id,
        addition_event_id,
        command.correction_of_id or addition_event_id,
        command.reason or "",
        command.operation_id,
        command.execution_status,
        Decimal(command.quantity) if command.quantity else None,
        command.unit,
        command.body,
        command.expected_revision,
    )
    return {
        "id": str(correction.id),
        "original_addition_event_id": str(correction.original_addition_event_id),
        "correction_of_id": str(correction.correction_of_id),
        "status": correction.execution_status,
    }


@router.post("/{session_id}/requirements/{requirement_id}/waivers", status_code=201)
def waive(
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    command: SessionCommand,
    db: Db,
    user: CurrentUser,
) -> dict:
    waiver = waiver_service.create_waiver(
        db,
        user,
        session_id,
        requirement_id,
        command.reason or "",
        command.operation_id or "",
        command.expected_revision,
    )
    return {"id": str(waiver.id), "status": waiver.status}


@router.post("/{session_id}/requirements/{requirement_id}/complete", status_code=200)
def complete_requirement(
    session_id: uuid.UUID,
    requirement_id: uuid.UUID,
    command: SessionCommand,
    db: Db,
    user: CurrentUser,
) -> dict:
    from brewing_api.application.phase3 import checklists as checklist_service

    requirement = checklist_service.complete_checklist(
        db,
        user,
        session_id,
        requirement_id,
        command.operation_id or "",
        command.expected_revision,
    )
    return {"id": str(requirement.requirement_id), "status": requirement.status}


@router.post("/timers/{timer_id}/pause", response_model=IdStatusResponse)
def pause_timer(
    timer_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    timer = timer_service.pause_timer(
        db,
        user,
        timer_id,
        command.expected_revision if command else None,
        command.operation_id if command else None,
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/timers/{timer_id}/resume", response_model=IdStatusResponse)
def resume_timer(
    timer_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    timer = timer_service.resume_timer(
        db,
        user,
        timer_id,
        command.expected_revision if command else None,
        command.operation_id if command else None,
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/timers/{timer_id}/complete", response_model=IdStatusResponse)
def complete_timer(
    timer_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    timer = timer_service.complete_timer(
        db,
        user,
        timer_id,
        command.expected_revision if command else None,
        command.operation_id if command else None,
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/timers/{timer_id}/cancel", response_model=IdStatusResponse)
def cancel_timer(
    timer_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    timer = timer_service.cancel_timer(
        db,
        user,
        timer_id,
        command.reason or "",
        command.expected_revision,
        command.operation_id,
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/timers/{timer_id}/acknowledge", response_model=IdStatusResponse)
def ack_timer(
    timer_id: uuid.UUID, db: Db, user: CurrentUser, command: SessionCommand | None = None
) -> IdStatusResponse:
    timer = timer_service.acknowledge_timer(
        db, user, timer_id, command.operation_id if command else None
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/timers/{timer_id}/replace", response_model=IdStatusResponse)
def replace_timer(
    timer_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    timer = timer_service.replace_timer(
        db,
        user,
        timer_id,
        command.reason or "",
        command.planned_duration_seconds or 60,
        command.operation_id,
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/timers/{timer_id}/extend", response_model=IdStatusResponse)
def extend_timer(
    timer_id: uuid.UUID, command: SessionCommand, db: Db, user: CurrentUser
) -> IdStatusResponse:
    timer = timer_service.extend_timer(
        db,
        user,
        timer_id,
        command.extra_seconds or 0,
        command.reason or "timer extension",
        command.operation_id,
    )
    return IdStatusResponse(id=timer.id, status=timer.status)


@router.post("/{session_id}/attachments", status_code=201)
async def upload_media(
    session_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    operation_id: Annotated[str, Form()],
    caption: Annotated[str | None, Form()] = None,
    stage_id: Annotated[uuid.UUID | None, Form()] = None,
) -> dict:
    attachment = media_service.upload_attachment(
        db, user, session_id, file, operation_id, caption, stage_id
    )
    return {"id": str(attachment.id), "status": attachment.status}


@router.get("/{session_id}/attachments/{attachment_id}")
def get_media(
    session_id: uuid.UUID, attachment_id: uuid.UUID, db: Db, user: CurrentUser
) -> Response:
    return media_service.retrieve_attachment(db, user, session_id, attachment_id)


@router.post("/{session_id}/attachments/{attachment_id}/remove")
def remove_media(
    session_id: uuid.UUID,
    attachment_id: uuid.UUID,
    command: SessionCommand,
    db: Db,
    user: CurrentUser,
) -> dict:
    attachment = media_service.soft_remove_attachment(
        db, user, session_id, attachment_id, command.reason or "removed", command.operation_id
    )
    return {"id": str(attachment.id), "status": attachment.status}


@router.post("/voice/proposals")
def voice_proposal(command: SessionCommand) -> dict:
    proposal = parse_voice_proposal(command.transcript or "")
    if proposal is None:
        return {"proposal": None, "committed": False}
    return {"proposal": proposal, "committed": False}


