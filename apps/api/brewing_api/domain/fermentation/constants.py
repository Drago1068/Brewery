OPERATION_SCHEMA_VERSION = "phase4-operation-v1"
PLAN_SCHEMA_VERSION = "phase4-plan-v1"
ENTRY_SCHEMA_VERSION = "phase4-entry-v1"
SESSION_STATE_SCHEMA_VERSION = "phase4-session-state-v1"
STABLE_GRAVITY_SCHEMA_VERSION = "phase4-stable-gravity-v1"
PACKAGING_READINESS_SCHEMA_VERSION = "phase4-packaging-readiness-v1"
TERMINAL_ADDITION_SCHEMA_VERSION = "phase4-terminal-addition-v1"

SESSION_STATUSES = frozenset(
    {
        "ACTIVE",
        "PAUSED",
        "FERMENTATION_COMPLETE",
        "CONDITIONING",
        "CONDITIONING_COMPLETE",
        "COMPLETION_ASSESSED",
        "HANDOFF_READY",
        "CLOSED",
        "ABORTED",
    }
)

STAGE_TYPES = frozenset(
    {
        "PITCH_CONFIRMED",
        "ACTIVE_FERMENTATION",
        "CONDITIONING",
        "HANDOFF_READY",
    }
)

CONDITIONING_MODES = frozenset(
    {
        "WARM_CONDITIONING",
        "COLD_CONDITIONING",
        "LAGERING",
        "COLD_CRASH",
    }
)

MEASUREMENT_TYPES = frozenset(
    {
        "FERMENTATION_GRAVITY",
        "FERMENTATION_TEMPERATURE",
        "FERMENTATION_PH",
        "CONDITIONING_TEMPERATURE",
    }
)
