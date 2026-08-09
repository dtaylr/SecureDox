"""Pydantic request/response models — the published HTTP contract."""

from __future__ import annotations

from .auth import LoginRequest, PrincipalOut, TokenResponse
from .audit import AuditEventOut
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
    DocumentReviewRequest,
    DocumentReviewResponse,
    DocumentSummary,
    DocumentSubmitRequest,
    DocumentSubmitResponse,
    DocumentUploadResponse,
    ExtractedFieldOut,
    FieldCorrection,
    ValidationResultOut,
)

__all__ = [
    "DocumentDetail",
    "DocumentListQuery",
    "DocumentReviewRequest",
    "DocumentReviewResponse",
    "DocumentSummary",
    "DocumentSubmitRequest",
    "DocumentSubmitResponse",
    "DocumentUploadResponse",
    "AuditEventOut",
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
