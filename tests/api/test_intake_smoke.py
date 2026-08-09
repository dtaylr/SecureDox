from __future__ import annotations

from tests.helpers.api_client import ApiClient
from tests.helpers.audit_log import (
    assert_audit_actions,
    assert_no_pii_in_audit,
    wait_for_audit_actions,
)
from tests.helpers.correlation import assert_correlation_id, correlation_id
from tests.helpers.document_factory import document_fixture
from tests.helpers.reporting import write_report
from tests.helpers.wait_for_job import wait_for_processing_state, wait_for_review_required


def test_user_can_upload_process_review_and_submit(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("api-smoke"))
    corr = correlation_id("upload")

    upload = admin_api.upload_document(fixture, correlation_id=corr)
    document_id = str(upload["id"])

    assert upload["status"] == "QUEUED"
    assert_correlation_id(str(upload["correlation_id"]))

    processing = wait_for_processing_state(admin_api, document_id)
    assert processing["status"] in {"QUEUED", "EXTRACTING", "VALIDATING", "VALIDATED"}

    review = wait_for_review_required(admin_api, document_id)
    assert review["status"] in {"REVIEW_REQUIRED", "VALIDATED", "REJECTED"}
    assert review["extracted_fields"]

    submitted = admin_api.submit_document(document_id)
    assert submitted["submitted"] is True

    events = wait_for_audit_actions(
        document_id,
        [
            "DOCUMENT_UPLOADED",
            "DOCUMENT_QUEUED",
            "EXTRACTION_COMPLETED",
            "VALIDATION_COMPLETED",
            "DOCUMENT_SUBMITTED",
        ],
    )
    assert_audit_actions(events, ["DOCUMENT_UPLOADED", "DOCUMENT_SUBMITTED"])
    assert_no_pii_in_audit(events)

    write_report(
        "api-smoke",
        {
            "document_id": document_id,
            "status": review["status"],
            "audit_actions": [event["action"] for event in events],
        },
    )
