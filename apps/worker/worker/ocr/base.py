"""The OCR adapter interface.

Every provider — mock, tesseract, a paid vendor — implements this one protocol,
which is what makes the reliability question testable: the same fixture set runs
against every adapter and the accuracy comparison is apples-to-apples.

Two deliberate design points:

* **Confidence is per field, not per document.** A document-level average hides
  the failure this platform exists to catch: a confidently-wrong SSN.
* **An adapter never raises for "found nothing".** Empty extraction is a valid
  result the rule engine handles. Exceptions are reserved for the adapter
  itself failing — timeout, bad credentials, corrupt input.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from securedox_shared import DocumentType, ExtractionResult


class OcrError(Exception):
    """Adapter failure. Retryable unless `permanent` is set.

    The distinction drives the worker's retry policy: a vendor timeout should
    be retried, a corrupt PDF never will be and must go straight to FAILED
    instead of burning the retry budget.
    """

    def __init__(self, message: str, *, permanent: bool = False, kind: str = "unknown") -> None:
        super().__init__(message)
        self.permanent = permanent
        #: Bounded vocabulary, used as a metric label — never the raw message.
        self.kind = kind


class OcrTimeoutError(OcrError):
    def __init__(self, message: str = "OCR provider timed out") -> None:
        super().__init__(message, permanent=False, kind="timeout")


class OcrUnprocessableError(OcrError):
    def __init__(self, message: str = "OCR provider could not read the document") -> None:
        super().__init__(message, permanent=True, kind="unprocessable")


@dataclass(frozen=True, slots=True)
class OcrRequest:
    document_id: UUID
    document_type: DocumentType
    mime_type: str
    content: bytes


class OcrAdapter(ABC):
    """Base class every provider implements."""

    #: Stable identifier used as a metric label and stored on the document row.
    name: str = "base"

    @abstractmethod
    async def extract(self, request: OcrRequest) -> ExtractionResult:
        """Pull fields out of a document.

        Implementations must return a result for every field in the document
        type's rule catalogue — using `None` for "not found" — so a missing key
        and a failed extraction are never confused downstream.
        """

    async def health(self) -> bool:
        """Whether the provider is reachable. Reported on the worker's probe."""
        return True
