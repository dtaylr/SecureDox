"""The regulated part: which fields each document type must carry, and how they
are checked.

Kept in shared code (not in the worker) because three consumers need the same
truth: the worker that applies the rules, the API that explains a rejection to
the user, and `tests/db` which asserts stored results match the rule catalogue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .enums import DocumentType, Severity


@dataclass(frozen=True, slots=True)
class FieldRule:
    """A single declarative validation rule.

    `rule_id` is stable and appears verbatim in `validation_results.rule_id`,
    in the API error payload and in Grafana's rejection-reason breakdown.
    """

    rule_id: str
    field_name: str
    severity: Severity
    message: str
    required: bool = True
    pattern: str | None = None
    min_length: int | None = None
    max_length: int | None = None
    is_date: bool = False
    not_in_future: bool = False


# Common building blocks -----------------------------------------------------
_SSN = r"^\d{3}-\d{2}-\d{4}$"
_CURRENCY = r"^\$?\d{1,3}(,\d{3})*(\.\d{2})?$"
_POLICY = r"^[A-Z]{2,4}-\d{6,10}$"
_MRN = r"^MRN\d{7}$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"


RULE_CATALOGUE: dict[DocumentType, tuple[FieldRule, ...]] = {
    DocumentType.LOAN: (
        FieldRule(
            "LOAN-001",
            "applicant_name",
            Severity.CRITICAL,
            "Applicant name is required",
            min_length=2,
            max_length=120,
        ),
        FieldRule("LOAN-002", "ssn", Severity.CRITICAL, "SSN must match NNN-NN-NNNN", pattern=_SSN),
        FieldRule(
            "LOAN-003",
            "loan_amount",
            Severity.HIGH,
            "Loan amount must be a currency value",
            pattern=_CURRENCY,
        ),
        FieldRule(
            "LOAN-004",
            "application_date",
            Severity.MEDIUM,
            "Application date must be ISO-8601 and not in the future",
            pattern=_DATE,
            is_date=True,
            not_in_future=True,
        ),
        FieldRule(
            "LOAN-005",
            "employer",
            Severity.LOW,
            "Employer is recommended for underwriting",
            required=False,
            max_length=120,
        ),
    ),
    DocumentType.INSURANCE: (
        FieldRule(
            "INS-001",
            "policy_number",
            Severity.CRITICAL,
            "Policy number must match XX-NNNNNN",
            pattern=_POLICY,
        ),
        FieldRule(
            "INS-002",
            "insured_name",
            Severity.CRITICAL,
            "Insured name is required",
            min_length=2,
            max_length=120,
        ),
        FieldRule(
            "INS-003",
            "effective_date",
            Severity.HIGH,
            "Effective date must be ISO-8601",
            pattern=_DATE,
            is_date=True,
        ),
        FieldRule(
            "INS-004",
            "claim_amount",
            Severity.MEDIUM,
            "Claim amount must be a currency value",
            required=False,
            pattern=_CURRENCY,
        ),
    ),
    DocumentType.MEDICAL: (
        FieldRule(
            "MED-001",
            "patient_mrn",
            Severity.CRITICAL,
            "Patient MRN must match MRNNNNNNNN",
            pattern=_MRN,
        ),
        FieldRule(
            "MED-002",
            "patient_name",
            Severity.CRITICAL,
            "Patient name is required",
            min_length=2,
            max_length=120,
        ),
        FieldRule(
            "MED-003",
            "date_of_service",
            Severity.HIGH,
            "Date of service must be ISO-8601 and not in the future",
            pattern=_DATE,
            is_date=True,
            not_in_future=True,
        ),
        FieldRule(
            "MED-004",
            "provider_npi",
            Severity.HIGH,
            "Provider NPI must be 10 digits",
            pattern=r"^\d{10}$",
        ),
    ),
    DocumentType.ONBOARDING: (
        FieldRule(
            "ONB-001",
            "full_name",
            Severity.CRITICAL,
            "Full name is required",
            min_length=2,
            max_length=120,
        ),
        FieldRule(
            "ONB-002",
            "start_date",
            Severity.HIGH,
            "Start date must be ISO-8601",
            pattern=_DATE,
            is_date=True,
        ),
        FieldRule(
            "ONB-003",
            "email",
            Severity.HIGH,
            "A valid work email is required",
            pattern=r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$",
        ),
        FieldRule(
            "ONB-004",
            "id_document_number",
            Severity.MEDIUM,
            "Government ID number is required",
            min_length=5,
            max_length=32,
        ),
    ),
}

#: Fields that must never appear in logs, metrics labels, error bodies or
#: Grafana panels. `packages/observability` redacts these centrally and
#: `tests/security/test_pii_redaction.py` proves it.
PII_FIELDS: frozenset[str] = frozenset(
    {"ssn", "patient_mrn", "id_document_number", "email", "date_of_birth"}
)


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    rule_id: str
    field_name: str
    passed: bool
    severity: Severity
    message: str
    observed: str | None = None


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    outcomes: tuple[RuleOutcome, ...] = field(default_factory=tuple)

    @property
    def failures(self) -> tuple[RuleOutcome, ...]:
        return tuple(o for o in self.outcomes if not o.passed)

    @property
    def is_accepted(self) -> bool:
        """A document is rejected by any HIGH or CRITICAL failure."""
        return not any(o.severity in (Severity.HIGH, Severity.CRITICAL) for o in self.failures)


def evaluate(doc_type: DocumentType, values: dict[str, str | None]) -> RuleEvaluation:
    """Apply the catalogue for `doc_type` to extracted field values.

    Pure and side-effect free so it can be property-tested without a database.
    """
    outcomes: list[RuleOutcome] = []
    for rule in RULE_CATALOGUE[doc_type]:
        raw = values.get(rule.field_name)
        value = raw.strip() if isinstance(raw, str) else None

        if not value:
            outcomes.append(
                RuleOutcome(
                    rule.rule_id,
                    rule.field_name,
                    not rule.required,
                    rule.severity,
                    rule.message if rule.required else "Optional field absent",
                )
            )
            continue

        problem = _first_problem(rule, value)
        outcomes.append(
            RuleOutcome(
                rule_id=rule.rule_id,
                field_name=rule.field_name,
                passed=problem is None,
                severity=rule.severity,
                message=problem or "OK",
                observed=None if rule.field_name in PII_FIELDS else value,
            )
        )
    return RuleEvaluation(tuple(outcomes))


def _first_problem(rule: FieldRule, value: str) -> str | None:
    if rule.min_length is not None and len(value) < rule.min_length:
        return f"{rule.message} (shorter than {rule.min_length})"
    if rule.max_length is not None and len(value) > rule.max_length:
        return f"{rule.message} (longer than {rule.max_length})"
    if rule.pattern is not None and not re.match(rule.pattern, value):
        return rule.message
    if rule.is_date:
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            return f"{rule.message} (unparseable date)"
        if rule.not_in_future and parsed > date.today():
            return f"{rule.message} (date is in the future)"
    return None
