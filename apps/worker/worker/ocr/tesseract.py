"""Local Tesseract adapter.

Real OCR against a local binary — no network, no vendor account. Tesseract
returns word-level confidences, which this adapter aggregates into the
per-field confidences the pipeline expects.

Field extraction is regex-over-full-text rather than layout-aware, which is a
genuine limitation: it works on the fixture set's labelled forms and would need
a layout model for arbitrary documents. Stated plainly here because a hidden
limitation in an OCR adapter becomes an unexplained accuracy cliff later.
"""

from __future__ import annotations

import asyncio
import io
import re
from typing import Any, Final

from securedox_shared import RULE_CATALOGUE, DocumentType, ExtractionResult
from worker.ocr.base import OcrAdapter, OcrError, OcrRequest, OcrTimeoutError, OcrUnprocessableError

#: Labels as they appear on the fixture forms, mapped to catalogue field names.
_FIELD_LABELS: Final[dict[DocumentType, dict[str, tuple[str, ...]]]] = {
    DocumentType.LOAN: {
        "applicant_name": ("applicant name", "applicant", "borrower"),
        "ssn": ("ssn", "social security", "social security number"),
        "loan_amount": ("loan amount", "amount requested", "principal"),
        "application_date": ("application date", "date of application", "dated"),
        "employer": ("employer", "current employer"),
    },
    DocumentType.INSURANCE: {
        "policy_number": ("policy number", "policy no", "policy #"),
        "insured_name": ("insured name", "insured", "policyholder"),
        "effective_date": ("effective date", "effective"),
        "claim_amount": ("claim amount", "amount claimed"),
    },
    DocumentType.MEDICAL: {
        "patient_mrn": ("mrn", "medical record number", "record number"),
        "patient_name": ("patient name", "patient"),
        "date_of_service": ("date of service", "service date", "dos"),
        "provider_npi": ("npi", "provider npi", "national provider"),
    },
    DocumentType.ONBOARDING: {
        "full_name": ("full name", "employee name", "name"),
        "start_date": ("start date", "commencement date"),
        "email": ("email", "work email", "e-mail"),
        "id_document_number": ("id number", "identification number", "document number"),
    },
}

#: Word-level confidence below this is treated as no read at all — Tesseract
#: emits -1 and single-digit scores for noise, and letting those through would
#: fabricate field values out of page artefacts.
_MIN_WORD_CONFIDENCE: Final = 30.0


class TesseractOcrAdapter(OcrAdapter):
    name = "tesseract"

    def __init__(self, *, timeout_seconds: int = 30, language: str = "eng") -> None:
        self._timeout = timeout_seconds
        self._language = language

    async def extract(self, request: OcrRequest) -> ExtractionResult:
        # Tesseract is CPU-bound and blocking: run it off the event loop or a
        # single large scan stalls every other job in the worker process.
        try:
            words = await asyncio.wait_for(
                asyncio.to_thread(self._run_tesseract, request.content, request.mime_type),
                timeout=self._timeout,
            )
        except TimeoutError as exc:
            raise OcrTimeoutError(f"Tesseract exceeded {self._timeout}s.") from exc

        text = " ".join(word for word, _ in words)
        page_confidence = self._mean([c for _, c in words if c >= _MIN_WORD_CONFIDENCE])

        fields: dict[str, str | None] = {}
        confidences: dict[str, float] = {}
        labels = _FIELD_LABELS[request.document_type]

        for rule in RULE_CATALOGUE[request.document_type]:
            value = self._find_labelled_value(text, labels.get(rule.field_name, ()))
            fields[rule.field_name] = value
            # Per-field confidence is the page mean discounted when the value
            # is absent — honest rather than precise, and flagged as such.
            confidences[rule.field_name] = page_confidence if value else 0.0

        return ExtractionResult(
            document_id=request.document_id,
            provider=self.name,
            fields=fields,
            confidences=confidences,
            page_count=1,
            duration_ms=0,
            # Tesseract's field confidences are page-level approximations, so
            # downstream consumers are told not to over-trust them.
            degraded=True,
        )

    def _run_tesseract(self, content: bytes, mime_type: str) -> list[tuple[str, float]]:
        """Blocking call into pytesseract. Returns (word, confidence) pairs."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise OcrError(
                "Tesseract support is not installed in this image.",
                permanent=True,
                kind="not_installed",
            ) from exc

        if mime_type == "application/pdf":
            raise OcrUnprocessableError(
                "The tesseract adapter handles images only; rasterise PDFs first."
            )

        try:
            image = Image.open(io.BytesIO(content))
            data: dict[str, Any] = pytesseract.image_to_data(
                image, lang=self._language, output_type=pytesseract.Output.DICT
            )
        except Exception as exc:
            raise OcrUnprocessableError(
                f"Could not decode the image: {type(exc).__name__}"
            ) from exc

        words: list[tuple[str, float]] = []
        for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
            cleaned = str(text).strip()
            if cleaned:
                words.append((cleaned, float(conf)))
        return words

    @staticmethod
    def _find_labelled_value(text: str, labels: tuple[str, ...]) -> str | None:
        """Take the text following a known label, up to the next label break."""
        for label in labels:
            pattern = re.compile(
                rf"{re.escape(label)}\s*[:\-]?\s*(.+?)(?=\s{{2,}}|$|\n)",
                re.IGNORECASE,
            )
            if match := pattern.search(text):
                value = match.group(1).strip()
                if value:
                    return value[:200]
        return None

    @staticmethod
    def _mean(values: list[float]) -> float:
        if not values:
            return 0.0
        # Tesseract reports 0-100; the pipeline works in 0.0-1.0.
        return min(max(sum(values) / len(values) / 100.0, 0.0), 1.0)

    async def health(self) -> bool:
        try:
            import pytesseract

            await asyncio.to_thread(pytesseract.get_tesseract_version)
        except Exception:
            return False
        return True
