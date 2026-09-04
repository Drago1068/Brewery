OPERATION_SCHEMA_VERSION = "phase4-operation-v1"
PLAN_SCHEMA_VERSION = "phase4-plan-v1"
ENTRY_SCHEMA_VERSION = "phase4-entry-v1"
SESSION_STATE_SCHEMA_VERSION = "phase4-session-state-v1"
STABLE_GRAVITY_SCHEMA_VERSION = "phase4-stable-gravity-v1"
PACKAGING_READINESS_SCHEMA_VERSION = "phase4-packaging-readiness-v1"
TERMINAL_ADDITION_SCHEMA_VERSION = "phase4-terminal-addition-v1"
MEASUREMENT_SCHEMA_VERSION = "phase4-measurement-v1"
DERIVED_GRAVITY_SCHEMA_VERSION = "phase4-derived-gravity-v1"
FERMENTATION_ELIGIBILITY_SCHEMA_VERSION = "phase4-fermentation-eligibility-v1"
CONDITIONING_ELIGIBILITY_SCHEMA_VERSION = "phase4-conditioning-eligibility-v1"
TIMER_SCHEMA_VERSION = "phase4-timer-v1"
REMINDER_SCHEMA_VERSION = "phase4-reminder-v1"

YEAST_SOURCE_FINISHING_STATUSES = frozenset(
    {
        "CLOSED",
        "HANDOFF_READY",
        "CONDITIONING_COMPLETE",
        "COMPLETION_ASSESSED",
    }
)

TIMER_NONTERMINAL = frozenset({"PENDING", "RUNNING", "PAUSED", "EXPIRED"})
REMINDER_UNRESOLVED = frozenset({"SCHEDULED", "DUE", "ACKNOWLEDGED", "EXPIRED"})

COMPLETION_OUTCOMES = frozenset(
    {
        "COMPLETION_ELIGIBLE",
        "COMPLETION_CONFIRMED",
        "COMPLETION_WAIVED",
        "COMPLETION_OVERRIDDEN",
        "INSUFFICIENT_EVIDENCE",
        "COMPLETION_INVALIDATED",
    }
)

SESSION_COMMANDS = frozenset(
    {
        "PauseFermentationSession",
        "ResumeFermentationSession",
        "AbortFermentationSession",
        "CompleteFermentation",
        "StartConditioning",
        "SkipConditioning",
        "CompleteConditioning",
        "AssessPackagingReadiness",
        "RecordPackagingReadinessHandoff",
        "CloseFermentationSession",
    }
)

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

MEASUREMENT_STAGE_BY_TYPE = {
    "FERMENTATION_GRAVITY": "ACTIVE_FERMENTATION",
    "FERMENTATION_TEMPERATURE": "ACTIVE_FERMENTATION",
    "FERMENTATION_PH": "ACTIVE_FERMENTATION",
    "CONDITIONING_TEMPERATURE": "CONDITIONING",
}

MEASUREMENT_TYPES = frozenset(MEASUREMENT_STAGE_BY_TYPE.keys())

GRAVITY_METHODS = frozenset({"HYDROMETER", "REFRACTOMETER", "OTHER"})
TEMPERATURE_METHODS = frozenset({"THERMOMETER", "PROBE", "OTHER"})
PH_METHODS = frozenset({"METER", "STRIP", "OTHER"})
MEASUREMENT_SOURCES = frozenset({"OBSERVED", "USER_ENTERED", "ESTIMATED", "UNKNOWN"})
