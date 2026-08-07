"""OCR adapters and the factory that selects one.

Selection happens once at worker startup, not per job: a misconfigured provider
should fail the container's readiness probe immediately rather than surfacing
as a per-document error on the hundredth upload.
"""

from __future__ import annotations

from worker.ocr.base import (
    OcrAdapter,
    OcrError,
    OcrRequest,
    OcrTimeoutError,
    OcrUnprocessableError,
)
from worker.ocr.mock import MockOcrAdapter
from worker.ocr.tesseract import TesseractOcrAdapter
from worker.ocr.vendor import VendorOcrAdapter


def build_adapter(
    provider: str,
    *,
    vendor_url: str = "",
    vendor_api_key: str = "",
    timeout_seconds: int = 30,
    degradation_rate: float = 0.0,
) -> OcrAdapter:
    """Return the configured adapter, or fail loudly on an unknown provider."""
    match provider:
        case "mock":
            return MockOcrAdapter(degradation_rate=degradation_rate)
        case "tesseract":
            return TesseractOcrAdapter(timeout_seconds=timeout_seconds)
        case "vendor":
            return VendorOcrAdapter(
                base_url=vendor_url,
                api_key=vendor_api_key,
                timeout_seconds=timeout_seconds,
            )
        case _:
            raise OcrError(f"Unknown OCR provider {provider!r}.", permanent=True, kind="config")


__all__ = [
    "MockOcrAdapter",
    "OcrAdapter",
    "OcrError",
    "OcrRequest",
    "OcrTimeoutError",
    "OcrUnprocessableError",
    "TesseractOcrAdapter",
    "VendorOcrAdapter",
    "build_adapter",
]
