"""Phase 4 closed command request schemas (P4-FR-077 / §30 / §33)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Phase4ClosedCommand(BaseModel):
    """Authoritative base for Phase 4 JSON mutation command bodies.

    Closed command schemas reject unknown fields (extra=\"forbid\").
    API normalization maps Pydantic ``extra_forbidden`` to ``422 UNKNOWN_FIELD``.
    """

    model_config = ConfigDict(extra="forbid")


def phase4_closed_command_models() -> tuple[type[Phase4ClosedCommand], ...]:
    """Return concrete Phase 4 closed command models for structural coverage."""
    # Import locally to avoid import cycles at module load.
    from brewing_api.presentation.routes import fermentation_sessions as routes

    models: list[type[Phase4ClosedCommand]] = []
    for name in dir(routes):
        obj = getattr(routes, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, Phase4ClosedCommand)
            and obj is not Phase4ClosedCommand
        ):
            models.append(obj)
    return tuple(sorted(models, key=lambda cls: cls.__name__))
