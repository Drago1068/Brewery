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

DEVIATION_SCHEMA_VERSION = "phase4-deviation-v1"
DEVIATION_CLASSES = frozenset(
    {
        "TEMPERATURE_EXCURSION",
        "MISSED_REMINDER_DEADLINE",
        "GRAVITY_TRAJECTORY",
        "STABLE_GRAVITY_BROKEN",
    }
)
DEVIATION_STATUSES = frozenset({"CURRENT", "SUPERSEDED"})
DEVIATION_ORIGINS = frozenset({"DERIVED", "USER_RECORDED"})

WAIVER_SCHEMA_VERSION = "phase4-waiver-v1"
READINESS_ELIGIBILITY_SCHEMA_VERSION = "phase4-readiness-eligibility-v1"
WAIVER_STATUSES = frozenset({"ACTIVE", "SUPERSEDED_BY_EVIDENCE", "SUPERSEDED"})
# §10.3 waivable catalog (stability is never waivable as a class).
WAIVABLE_REQUIREMENT_CLASSES = frozenset(
    {
        "FERMENTATION_TEMPERATURE",
        "FERMENTATION_PH",
        "CONDITIONING_TEMPERATURE",
        "CONDITIONING_DURATION",
        "PLANNED_ADDITION",
        "ATTENUATION_TARGET",
        "ORIGINAL_GRAVITY_KNOWN",
    }
)
NEVER_WAIVABLE_REQUIREMENT_KEYS = frozenset(
    {
        "FERMENTATION_GRAVITY_STABILITY",
        "PITCHED_AT",
        "YEAST_ADDITION_NOTE",
        "YEAST_ADDITION_FACT",
        "OWNERSHIP",
        "IDEMPOTENCY",
        "CSRF",
        "PREFLIGHT",
        "SNAPSHOT_RECEIPT",
    }
)
ORIGINAL_GRAVITY_KNOWN = "ORIGINAL_GRAVITY_KNOWN"
OG_WAIVER_ALLOWED_STATUSES = frozenset(
    {"CONDITIONING_COMPLETE", "COMPLETION_ASSESSED", "HANDOFF_READY"}
)
CHECKPOINT_WAIVER_ALLOWED_STATUSES = frozenset(
    {
        "ACTIVE",
        "PAUSED",
        "FERMENTATION_COMPLETE",
        "CONDITIONING",
        "CONDITIONING_COMPLETE",
        "COMPLETION_ASSESSED",
        "HANDOFF_READY",
    }
)
