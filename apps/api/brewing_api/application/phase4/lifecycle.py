"""Authoritative fermentation session lifecycle transition guards (§9.4)."""

from __future__ import annotations

from brewing_api.domain.fermentation.constants import SESSION_STATUSES

# §9.5 allowlist: command -> allowed session statuses
_COMMAND_ALLOWLIST: dict[str, frozenset[str]] = {
    "PauseFermentationSession": frozenset({"ACTIVE", "CONDITIONING"}),
    "ResumeFermentationSession": frozenset({"PAUSED"}),
    "AbortFermentationSession": frozenset(
        {"ACTIVE", "PAUSED", "FERMENTATION_COMPLETE", "CONDITIONING", "CONDITIONING_COMPLETE"}
    ),
    "CompleteFermentation": frozenset({"ACTIVE"}),
    "StartConditioning": frozenset({"FERMENTATION_COMPLETE"}),
    "SkipConditioning": frozenset({"FERMENTATION_COMPLETE"}),
    "CompleteConditioning": frozenset({"CONDITIONING"}),
    "AssessPackagingReadiness": frozenset(
        {"CONDITIONING_COMPLETE", "COMPLETION_ASSESSED", "HANDOFF_READY", "CLOSED"}
    ),
    "RecordPackagingReadinessHandoff": frozenset(
        {"COMPLETION_ASSESSED", "HANDOFF_READY", "CLOSED"}
    ),
    "CloseFermentationSession": frozenset({"HANDOFF_READY"}),
}

_TERMINAL_SESSION_STATUSES = frozenset({"CLOSED", "ABORTED"})


def assert_command_allowed(command: str, status: str) -> None:
    if status not in SESSION_STATUSES:
        raise ValueError(f"Unknown session status {status}")
    if status in _TERMINAL_SESSION_STATUSES:
        if status == "CLOSED" and command in {
            "AssessPackagingReadiness",
            "RecordPackagingReadinessHandoff",
        }:
            return
        from brewing_api.application.errors import ConflictError

        raise ConflictError(
            "Session is in a terminal state",
            code="TERMINAL_SESSION" if status == "CLOSED" else "INVALID_TRANSITION",
        )
    allowed = _COMMAND_ALLOWLIST.get(command)
    if allowed is None or status not in allowed:
        from brewing_api.application.errors import ConflictError

        raise ConflictError("Invalid session transition", code="INVALID_TRANSITION")
