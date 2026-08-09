from __future__ import annotations

from tests.helpers.api_client import ApiClient
from tests.helpers.audit_log import wait_for_audit_actions
from tests.helpers.correlation import correlation_id
from tests.helpers.db_client import get_document
from tests.helpers.document_factory import document_fixture
from tests.helpers.wait_for_job import wait_for_review_required


def test_db_helper_validates_document_record(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("db-smoke"))
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])

    reviewed = wait_for_review_required(admin_api, document_id)
    row = get_document(document_id)

    assert row is not None
    assert row["id"] == document_id
    assert row["tenant_id"] == "acme-lending"
    assert row["status"] == reviewed["status"]
    assert row["original_filename"] == fixture.filename

    events = wait_for_audit_actions(document_id, ["DOCUMENT_UPLOADED", "VALIDATION_COMPLETED"])
    assert len(events) >= 2
