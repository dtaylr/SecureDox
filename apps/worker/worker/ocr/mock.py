"""Deterministic OCR adapter — the default for local development and CI.

Not a stub that returns constants. It is a *simulator* that reproduces the
failure modes of real OCR, because those failures are what the test suites
exist to detect:

* **Confidently wrong.** A field that transcribes `1` as `l` while reporting
  0.95 confidence. Rules pass, the data is wrong, and only a confidence-aware
  check or a human catches it.
* **Low-confidence-but-right.** The inverse, which drives false-positive rates
  in any "flag anything below 0.8" review queue.
* **Dropped fields.** A field the engine simply does not see.

Behaviour is keyed off the document's own bytes, so the same fixture always
produces the same extraction — a flaky OCR adapter would make every downstream
test flaky and untrustworthy.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

from securedox_shared import RULE_CATALOGUE, DocumentType, ExtractionResult
from worker.ocr.base import OcrAdapter, OcrRequest, OcrUnprocessableError

#: Fixtures embed their expected extraction as a JSON block, so a test author
#: writes the ground truth next to the document instead of in a parallel file
#: that silently drifts.
_FIXTURE_MARKER: Final = b"SECUREDOX-FIXTURE:"


def _json_object_after(data: bytes, offset: int) -> bytes | None:
    """Return the balanced JSON object starting at `offset`, or None.

    A regex cannot do this. `\\{.*?\\}` stops at the first closing brace and so
    truncates any nested object — which is every realistic fixture, since
    `{"fields": {...}}` is the normal shape. Braces are counted instead, with
    string literals and escapes skipped so a `}` inside a value does not end
    the scan early.
    """
    while offset < len(data) and data[offset : offset + 1].isspace():
        offset += 1
    if data[offset : offset + 1] != b"{":
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(offset, len(data)):
        char = data[index : index + 1]
        if in_string:
            if escaped:
                escaped = False
            elif char == b"\\":
                escaped = True
            elif char == b'"':
                in_string = False
            continue
        if char == b'"':
            in_string = True
        elif char == b"{":
            depth += 1
        elif char == b"}":
            depth -= 1
            if depth == 0:
                return data[offset : index + 1]
    return None


#: Realistic per-type defaults for when a document carries no fixture block.
_DEFAULT_FIELDS: Final[dict[DocumentType, dict[str, str]]] = {
    DocumentType.LOAN: {
        "applicant_name": "Jordan Rivera",
        "ssn": "123-45-6789",
        "loan_amount": "$45,000.00",
        "application_date": "2026-01-15",
        "employer": "Contoso Manufacturing",
    },
    DocumentType.INSURANCE: {
        "policy_number": "AB-1234567",
        "insured_name": "Sam Okafor",
        "effective_date": "2026-02-01",
        "claim_amount": "$1,250.00",
    },
    DocumentType.MEDICAL: {
        "patient_mrn": "MRN1234567",
        "patient_name": "Alex Chen",
        "date_of_service": "2026-01-20",
        "provider_npi": "1234567890",
    },
    DocumentType.ONBOARDING: {
        "full_name": "Priya Nair",
        "start_date": "2026-03-01",
        "email": "priya.nair@example.com",
        "id_document_number": "X1234567",
    },
}

#: Confusions a real engine makes. Applied at high confidence on purpose.
_GLYPH_CONFUSIONS: Final[tuple[tuple[str, str], ...]] = (
    ("1", "l"),
    ("0", "O"),
    ("5", "S"),
    ("8", "B"),
)


class MockOcrAdapter(OcrAdapter):
    name = "mock"

    def __init__(self, *, degradation_rate: float = 0.0) -> None:
        #: 0.0 keeps CI deterministic and clean. Chaos scenarios raise it to
        #: prove the pipeline degrades gracefully rather than corrupting data.
        self._degradation_rate = degradation_rate

    async def extract(self, request: OcrRequest) -> ExtractionResult:
        if not request.content:
            raise OcrUnprocessableError("Document is empty.")

        fixture = self._read_fixture(request.content)
        fields: dict[str, str | None]
        confidences: dict[str, float]

        if fixture is not None:
            fields, confidences = self._from_fixture(fixture, request.document_type)
        else:
            fields, confidences = self._synthesise(request)

        # Every catalogue field is present, `None` where nothing was found —
        # the contract the rule engine relies on.
        for rule in RULE_CATALOGUE[request.document_type]:
            fields.setdefault(rule.field_name, None)
            confidences.setdefault(rule.field_name, 0.0)

        seed = self._seed(request.content)
        return ExtractionResult(
            document_id=request.document_id,
            provider=self.name,
            fields=fields,
            confidences=confidences,
            page_count=1 + seed % 4,
            duration_ms=120 + seed % 400,
            degraded=any(c < 0.5 for c in confidences.values()),
        )

    # --- fixture path ------------------------------------------------------

    @staticmethod
    def _read_fixture(content: bytes) -> dict[str, Any] | None:
        """Pull an embedded ground-truth block out of a fixture document."""
        marker = content.find(_FIXTURE_MARKER)
        if marker == -1:
            return None

        block = _json_object_after(content, marker + len(_FIXTURE_MARKER))
        if block is None:
            # A malformed fixture is an authoring error, and failing loudly
            # beats silently falling through to synthetic data that hides it.
            raise OcrUnprocessableError("Fixture marker is not followed by a balanced JSON object.")

        try:
            parsed = json.loads(block)
        except json.JSONDecodeError as exc:
            raise OcrUnprocessableError(f"Fixture block is not valid JSON: {exc.msg}") from exc
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _from_fixture(
        fixture: dict[str, Any], document_type: DocumentType
    ) -> tuple[dict[str, str | None], dict[str, float]]:
        raw_fields = fixture.get("fields", {})
        raw_confidences = fixture.get("confidences", {})

        fields: dict[str, str | None] = {
            str(k): (None if v is None else str(v)) for k, v in raw_fields.items()
        }
        # An unspecified confidence defaults high: a fixture author writing
        # only `fields` is describing a clean read.
        confidences = {name: float(raw_confidences.get(name, 0.95)) for name in fields}
        del document_type  # catalogue backfill happens in the caller
        return fields, confidences

    # --- synthetic path ----------------------------------------------------

    def _synthesise(self, request: OcrRequest) -> tuple[dict[str, str | None], dict[str, float]]:
        """Derive a plausible extraction from the document's own bytes."""
        seed = self._seed(request.content)
        base = dict(_DEFAULT_FIELDS[request.document_type])

        fields: dict[str, str | None] = {}
        confidences: dict[str, float] = {}

        for index, (name, value) in enumerate(base.items()):
            bucket = (seed >> (index * 3)) % 100
            threshold = self._degradation_rate * 100

            if bucket < threshold * 0.3:
                # Dropped entirely: the engine never saw the field.
                fields[name] = None
                confidences[name] = 0.0
            elif bucket < threshold:
                # The dangerous case: wrong value, high confidence.
                fields[name] = self._confuse(value, seed + index)
                confidences[name] = 0.88 + (bucket % 10) / 100
            else:
                fields[name] = value
                # Never a flat 1.0 — a real engine is never certain, and a
                # constant would let a threshold bug pass unnoticed.
                confidences[name] = 0.82 + ((seed >> index) % 17) / 100

        return fields, confidences

    @staticmethod
    def _confuse(value: str, seed: int) -> str:
        """Apply one glyph substitution, the way a real engine misreads."""
        for index, (source, target) in enumerate(_GLYPH_CONFUSIONS):
            if source in value and (seed + index) % 2 == 0:
                return value.replace(source, target, 1)
        return value[:-1] + "?" if value else value

    @staticmethod
    def _seed(content: bytes) -> int:
        """Stable per-document seed: same bytes, same extraction, always."""
        return int.from_bytes(hashlib.sha256(content).digest()[:4], "big")
