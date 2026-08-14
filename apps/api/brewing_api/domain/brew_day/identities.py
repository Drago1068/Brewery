import uuid

from brewing_api.domain.brew_day.constants import (
    LEGACY_IDENTITY_NAMESPACE,
    PLAN_IDENTITY_NAMESPACE,
    RUNTIME_REQUIREMENTS_VERSION,
)


def plan_step_id(
    recipe_version_id: uuid.UUID,
    source_kind: str,
    stable_source_discriminator: str,
    canonical_stage_type: str,
    expansion_rank: int,
    planned_same_type_ordinal: int,
) -> uuid.UUID:
    name = (
        f"phase3-plan-v1:{str(recipe_version_id).lower()}:{source_kind}:"
        f"{stable_source_discriminator.lower()}:{canonical_stage_type}:"
        f"{expansion_rank}:{planned_same_type_ordinal}"
    )
    return uuid.uuid5(PLAN_IDENTITY_NAMESPACE, name)


def requirement_template_id(
    plan_step_id_value: uuid.UUID,
    requirement_class: str,
    definition_key: str,
) -> uuid.UUID:
    name = (
        f"phase3-req-tpl-v1:{str(plan_step_id_value).lower()}:{requirement_class}:{definition_key}"
    )
    return uuid.uuid5(PLAN_IDENTITY_NAMESPACE, name)


def runtime_requirement_id(
    stage_instance_id: uuid.UUID,
    template_id: uuid.UUID,
    requirement_class: str,
) -> uuid.UUID:
    name = (
        f"{RUNTIME_REQUIREMENTS_VERSION}:{str(stage_instance_id).lower()}:"
        f"{str(template_id).lower()}:{requirement_class}"
    )
    return uuid.uuid5(PLAN_IDENTITY_NAMESPACE, name)


def legacy_plan_step_id(recipe_version_id: uuid.UUID, stage_type: str) -> uuid.UUID:
    return uuid.uuid5(
        LEGACY_IDENTITY_NAMESPACE,
        f"legacy-phase1a:plan:{str(recipe_version_id).lower()}:{stage_type}:1",
    )


def legacy_stage_instance_id(brew_session_id: uuid.UUID, stage_type: str) -> uuid.UUID:
    return uuid.uuid5(
        LEGACY_IDENTITY_NAMESPACE,
        f"legacy-phase1a:stage:{str(brew_session_id).lower()}:{stage_type}:1",
    )
