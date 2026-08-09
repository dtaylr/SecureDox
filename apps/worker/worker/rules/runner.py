"""Applying the rule catalogue to an extraction, and persisting the outcome.

The rule *logic* lives in `securedox_shared.rules` and is pure. This module is
the impure half: it turns a `RuleEvaluation` into database rows, metrics and a
rejection reason a human can read.

It also adds the check the pure rules cannot make — the confidence overlay. A
rule can only see the value it was given; it cannot know the OCR engine was
only 55% sure of it. A document whose every rule passes on low-confidence
values is exactly the "silently wrong" case this platform exists to surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from securedox_observability import metrics
from securedox_shared import (
    PII_FIELDS,
    DocumentStatus,
    DocumentType,
    ExtractionResult,
    RuleEvaluation,
    Severity,
    ValidationStatus,
    evaluate,
)


@dataclass(frozen=True, slots=True)
class ValidationVerdict:
    """The decision, plus everything needed to explain it."""

    evaluation: RuleEvaluation
    status: DocumentStatus
    rejection_reason: str | None
    #: Fields that passed their rules but are below the confidence floor.
    low_confidence_fields: tuple[str, ...]

    @property
    def needs_human_review(self) -> bool:
        """Accepted, but not safely: a reviewer should look before it is used."""
        return self.status == DocumentStatus.VALIDATED and bool(self.low_confidence_fields)


class RuleRunner:
    def __init__(self, *, confidence_threshold: float = 0.80) -> None:
        self._threshold = confidence_threshold

    def run(self, document_type: DocumentType, extraction: ExtractionResult) -> ValidationVerdict:
        evaluation = evaluate(document_type, extraction.fields)

        for outcome in evaluation.outcomes:
            metrics.validation_outcomes_total.labels(
                rule_id=outcome.rule_id,
                severity=outcome.severity.value,
                outcome="pass" if outcome.passed else "fail",
            ).inc()

        for confidence in extraction.confidences.values():
            metrics.ocr_field_confidence.labels(document_type=document_type.value).observe(
                confidence
            )

        low_confidence = self._low_confidence_fields(evaluation, extraction)

        if evaluation.is_accepted and low_confidence:
            return ValidationVerdict(
                evaluation=evaluation,
                status=DocumentStatus.REVIEW_REQUIRED,
                rejection_reason="Manual review required for low-confidence OCR fields.",
                low_confidence_fields=low_confidence,
            )

        if evaluation.is_accepted:
            return ValidationVerdict(
                evaluation=evaluation,
                status=DocumentStatus.VALIDATED,
                rejection_reason=None,
                low_confidence_fields=low_confidence,
            )

        return ValidationVerdict(
            evaluation=evaluation,
            status=DocumentStatus.REJECTED,
            rejection_reason=self._explain(evaluation),
            low_confidence_fields=low_confidence,
        )

    def _low_confidence_fields(
        self, evaluation: RuleEvaluation, extraction: ExtractionResult
    ) -> tuple[str, ...]:
        """Passing fields the OCR engine was not confident about.

        Only passing ones: a failing field is already surfaced by its rule, and
        listing it twice buries the signal that matters.
        """
        passed = {o.field_name for o in evaluation.outcomes if o.passed}
        return tuple(
            sorted(
                name
                for name, confidence in extraction.confidences.items()
                if name in passed and 0.0 < confidence < self._threshold
            )
        )

    @staticmethod
    def _explain(evaluation: RuleEvaluation) -> str:
        """Build a user-facing rejection reason.

        Ordered by severity so the most important reason leads, and truncated
        because this string ends up in a UI toast and a mobile push. Rule
        messages only — never an observed value, which may be an SSN.
        """
        order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3}
        blocking = sorted(
            (f for f in evaluation.failures if f.severity in (Severity.HIGH, Severity.CRITICAL)),
            key=lambda f: (order.get(f.severity, 9), f.rule_id),
        )
        if not blocking:
            return "Validation failed."

        shown = blocking[:3]
        reason = "; ".join(f"{f.rule_id}: {f.message}" for f in shown)
        if len(blocking) > len(shown):
            reason += f" (and {len(blocking) - len(shown)} more)"
        return reason[:1000]


def outcome_rows(verdict: ValidationVerdict) -> list[dict[str, object]]:
    """Project a verdict into `validation_results` row payloads.

    `observed` is dropped for PII fields — the rule engine already withholds
    it, and this is the belt to that suspenders.
    """
    rows: list[dict[str, object]] = []
    for outcome in verdict.evaluation.outcomes:
        blocking = not outcome.passed and outcome.severity in (
            Severity.HIGH,
            Severity.CRITICAL,
        )
        if outcome.passed:
            status = ValidationStatus.PASS
        elif blocking:
            status = ValidationStatus.FAIL
        else:
            status = ValidationStatus.WARN

        rows.append(
            {
                "rule_id": outcome.rule_id,
                "field_name": outcome.field_name,
                "status": status,
                "severity": outcome.severity,
                "message": outcome.message,
                "observed": None if outcome.field_name in PII_FIELDS else outcome.observed,
                "is_blocking": blocking,
            }
        )
    return rows
