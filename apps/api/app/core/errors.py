"""Error taxonomy and the single JSON error shape.

Every failure the API emits — validation, authz, upload gate, unhandled crash —
serialises to the same envelope, because the web app, the mobile app, the
Playwright specs and the Pact contract all parse one shape:

    {"error": {"code": "...", "message": "...", "correlation_id": "...",
               "details": [...]}}

`code` is a stable machine-readable token; `message` is human text that may be
reworded without breaking a client. Clients switch on `code`, never on
`message`, and `tests/contract` enforces that the codes below are exhaustive.
"""

from __future__ import annotations

from typing import Any

from fastapi import status


class AppError(Exception):
    """Base for every error the application raises deliberately.

    Anything that is *not* an AppError reaching the handler is a bug, and is
    reported as INTERNAL_ERROR with no detail — an unexpected exception's
    message is untrusted output that may contain document content.
    """

    code: str = "INTERNAL_ERROR"
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or []


# --- 4xx: the caller can fix it -------------------------------------------


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND
    message = "The requested resource does not exist."


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "The request payload failed validation."


class UnauthorizedError(AppError):
    code = "UNAUTHORIZED"
    http_status = status.HTTP_401_UNAUTHORIZED
    message = "Authentication is required."


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    http_status = status.HTTP_403_FORBIDDEN
    message = "You do not have access to this resource."


class TenantMismatchError(ForbiddenError):
    """Cross-tenant access attempt.

    Reported as a plain 403 with no hint that the resource exists — a 404-vs-403
    difference is an enumeration oracle. Distinct class so the audit log and
    the security dashboard can count these separately from ordinary 403s.
    """

    code = "FORBIDDEN"


class UnsupportedMediaTypeError(AppError):
    code = "UNSUPPORTED_MEDIA_TYPE"
    http_status = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    message = "That file type is not accepted."


class PayloadTooLargeError(AppError):
    code = "PAYLOAD_TOO_LARGE"
    http_status = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    message = "The uploaded file exceeds the size limit."


class DuplicateDocumentError(AppError):
    code = "DUPLICATE_DOCUMENT"
    http_status = status.HTTP_409_CONFLICT
    message = "An identical document has already been uploaded."


class InvalidStateTransitionError(AppError):
    code = "INVALID_STATE_TRANSITION"
    http_status = status.HTTP_409_CONFLICT
    message = "The document is not in a state that allows this operation."


class RateLimitedError(AppError):
    code = "RATE_LIMITED"
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    message = "Too many requests. Retry later."


# --- 5xx: we have to fix it ------------------------------------------------


class StorageError(AppError):
    code = "STORAGE_UNAVAILABLE"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "Document storage is unavailable."


class QueueError(AppError):
    code = "QUEUE_UNAVAILABLE"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "The processing queue is unavailable."
