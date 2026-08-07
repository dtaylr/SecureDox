"""Domain enums shared by the API, the worker and every Python test suite.

These names are part of the public contract: they appear in the OpenAPI schema,
the queue message schema, Grafana dashboard queries and the Cucumber feature
files. Renaming a member is a breaking change — add a migration and bump the
contract version instead.
"""

from __future__ import annotations

from enum import StrEnum


class DocumentType(StrEnum):
    LOAN = "LOAN"
    INSURANCE = "INSURANCE"
    MEDICAL = "MEDICAL"
    ONBOARDING = "ONBOARDING"


class DocumentStatus(StrEnum):
    """Intake state machine.

    RECEIVED -> QUEUED -> EXTRACTING -> VALIDATING -> VALIDATED | REJECTED
    Any state may fall to FAILED on an unrecoverable error; QUARANTINED is a
    terminal state reserved for files that fail the malware/mime gate.
    """

    RECEIVED = "RECEIVED"
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATUSES


_TERMINAL_STATUSES = frozenset(
    {
        DocumentStatus.VALIDATED,
        DocumentStatus.REJECTED,
        DocumentStatus.FAILED,
        DocumentStatus.QUARANTINED,
    }
)

#: Legal transitions. The worker and the API both enforce this map, and
#: `tests/db/suites/test_state_machine.py` asserts no row ever violated it.
ALLOWED_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.RECEIVED: frozenset(
        {DocumentStatus.QUEUED, DocumentStatus.QUARANTINED, DocumentStatus.FAILED}
    ),
    DocumentStatus.QUEUED: frozenset({DocumentStatus.EXTRACTING, DocumentStatus.FAILED}),
    DocumentStatus.EXTRACTING: frozenset({DocumentStatus.VALIDATING, DocumentStatus.FAILED}),
    DocumentStatus.VALIDATING: frozenset(
        {DocumentStatus.VALIDATED, DocumentStatus.REJECTED, DocumentStatus.FAILED}
    ),
    DocumentStatus.VALIDATED: frozenset(),
    DocumentStatus.REJECTED: frozenset(),
    DocumentStatus.FAILED: frozenset({DocumentStatus.QUEUED}),  # operator-triggered replay
    DocumentStatus.QUARANTINED: frozenset(),
}


def can_transition(current: DocumentStatus, target: DocumentStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


class ValidationStatus(StrEnum):
    PASS = "PASS"  # noqa: S105 - a validation outcome, not a password
    WARN = "WARN"
    FAIL = "FAIL"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FieldSource(StrEnum):
    OCR = "OCR"
    MANUAL = "MANUAL"
    DERIVED = "DERIVED"


class AuditAction(StrEnum):
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_QUEUED = "DOCUMENT_QUEUED"
    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DOCUMENT_QUARANTINED = "DOCUMENT_QUARANTINED"
    FIELD_CORRECTED = "FIELD_CORRECTED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
