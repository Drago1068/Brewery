from sqlalchemy import select
from sqlalchemy.orm import Session

from brewing_api.domain.brew_sessions.models import BrewSession, BrewStage


def is_legacy_plan(session: BrewSession) -> bool:
    return (
        session.plan_kind in {None, "LEGACY_MASH_ONLY"}
        or session.materialization_rule_version is None
    )


def first_mash_stage(db: Session, session: BrewSession) -> BrewStage | None:
    stages = list(
        db.scalars(
            select(BrewStage)
            .where(BrewStage.brew_session_id == session.id)
            .order_by(BrewStage.occurrence_number, BrewStage.created_at)
        ).all()
    )
    mashes = [item for item in stages if item.canonical_stage_type == "MASH" or item.name == "MASH"]
    if not mashes:
        return None
    pending = [item for item in mashes if item.status == "PENDING"]
    if pending:
        return pending[0]
    return mashes[0]
