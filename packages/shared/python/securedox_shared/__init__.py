"""Shared domain vocabulary for every SecureDox Python component.

Import from the package root — the module layout below is an implementation
detail and may be reorganised without a contract bump:

    from securedox_shared import DocumentStatus, IntakeJob, evaluate
"""

from __future__ import annotations

from .enums import (
    ALLOWED_TRANSITIONS,
    AuditAction,
    DocumentStatus,
    DocumentType,
    FieldSource,
    Severity,
    ValidationStatus,
    can_transition,
)
from .messages import SCHEMA_VERSION, ExtractionResult, IntakeJob
from .rules import (
    PII_FIELDS,
    RULE_CATALOGUE,
    FieldRule,
    RuleEvaluation,
    RuleOutcome,
    evaluate,
)

__version__ = "0.1.0"

__all__ = [
    "ALLOWED_TRANSITIONS",
    "PII_FIELDS",
    "RULE_CATALOGUE",
    "SCHEMA_VERSION",
    "AuditAction",
    "DocumentStatus",
    "DocumentType",
    "ExtractionResult",
    "FieldRule",
    "FieldSource",
    "IntakeJob",
    "RuleEvaluation",
    "RuleOutcome",
    "Severity",
    "ValidationStatus",
    "__version__",
    "can_transition",
    "evaluate",
]
