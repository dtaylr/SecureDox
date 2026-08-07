"""Pydantic request/response models — the published HTTP contract."""

from __future__ import annotations

from .auth import LoginRequest, PrincipalOut, TokenResponse
from .common import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    Page,
    PageMeta,
    ReadinessResponse,
)
from .document import (
    DocumentDetail,
    DocumentListQuery,
    DocumentSummary,
    DocumentUploadResponse,
    ExtractedFieldOut,
    FieldCorrection,
    ValidationResultOut,
)

__all__ = [
    "DocumentDetail",
    "DocumentListQuery",
    "DocumentSummary",
    "DocumentUploadResponse",
    "ErrorBody",
    "ErrorDetail",
    "ErrorResponse",
    "ExtractedFieldOut",
    "FieldCorrection",
    "HealthResponse",
    "LoginRequest",
    "Page",
    "PageMeta",
    "PrincipalOut",
    "ReadinessResponse",
    "TokenResponse",
    "ValidationResultOut",
]
