from __future__ import annotations

from typing import Any

from tests.helpers.api_client import ApiClient
from tests.helpers.retry import wait_until


def wait_for_processing_state(api: ApiClient, document_id: str) -> dict[str, Any]:
    return wait_until(
        lambda: api.get_document(document_id),
        lambda document: document["status"] in {"QUEUED", "EXTRACTING", "VALIDATING", "VALIDATED"},
        description=f"document {document_id} to enter processing",
    )


def wait_for_review_required(api: ApiClient, document_id: str) -> dict[str, Any]:
    return wait_until(
        lambda: api.get_document(document_id),
        lambda document: document["status"] in {"VALIDATED", "REJECTED"},
        description=f"document {document_id} to be ready for review",
    )
