# -*- coding: utf-8 -*-
"""FPF Autonomous Engineering Coordinator Core Dispatch Package."""
from .states import Phase, Decision, HUMAN_GATE_PHASES, IN_FLIGHT_PHASES, TERMINAL_PHASES
from .core import (
    Target,
    CanonicalSnapshot,
    TaskPacket,
    make_idempotency_key,
    next_action,
    make_packet,
    canonical_url,
    validate_sha,
    ROLES,
    ALLOWED_ACTIONS,
)
from .journal import (
    StateJournal,
    TaskRecord,
    Lease,
    IntentRecord,
    ConcurrencyConflictError,
    AttemptLimitExceededError,
    TaskNotFoundError,
)
from .events import (
    EventBatch,
    NormalizedEvent,
    EventValidationError,
    build_event,
    normalize_event,
    prepare_events,
)
from .reducer import Reduction, reduce_events
from .reconcile import reconcile_projection

__all__ = [
    "Phase",
    "Decision",
    "HUMAN_GATE_PHASES",
    "IN_FLIGHT_PHASES",
    "TERMINAL_PHASES",
    "Target",
    "CanonicalSnapshot",
    "TaskPacket",
    "make_idempotency_key",
    "next_action",
    "make_packet",
    "canonical_url",
    "validate_sha",
    "ROLES",
    "ALLOWED_ACTIONS",
    "StateJournal",
    "TaskRecord",
    "Lease",
    "IntentRecord",
    "ConcurrencyConflictError",
    "AttemptLimitExceededError",
    "TaskNotFoundError",
    "EventBatch",
    "NormalizedEvent",
    "EventValidationError",
    "build_event",
    "normalize_event",
    "prepare_events",
    "Reduction",
    "reduce_events",
    "reconcile_projection",
]
