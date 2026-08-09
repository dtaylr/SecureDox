from __future__ import annotations

from tests.helpers.api_client import ApiClient
from tests.helpers.audit_log import assert_no_pii_in_audit, wait_for_audit_actions
from tests.helpers.correlation import correlation_id
from tests.helpers.db_client import (
    audit_events_for_document,
    documents_by_checksum,
    extracted_fields_for_document,
    get_document,
    validation_results_for_document,
)
from tests.helpers.document_factory import DEFAULT_FIELDS, document_fixture
from tests.helpers.wait_for_job import wait_for_review_required


def test_document_row_created_after_upload(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("db-created"))
    upload = admin_api.upload_document(fixture)

    row = get_document(str(upload["id"]))

    assert row is not None
    assert row["tenant_id"] == "acme-lending"
    assert row["original_filename"] == fixture.filename
    assert row["status"] == "QUEUED"


def test_processing_status_updates_are_persisted(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("db-status"))
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])

    api_document = wait_for_review_required(admin_api, document_id)
    row = get_document(document_id)

    assert row is not None
    assert row["status"] == api_document["status"]
    assert row["processed_at"] is not None


def test_duplicate_hash_is_rejected(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("db-duplicate"))
    first = admin_api.upload_document(fixture)
    row = get_document(str(first["id"]))
    assert row is not None

    duplicate = admin_api.upload_document_response(fixture)

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_DOCUMENT"
    rows = documents_by_checksum("acme-lending", str(row["checksum_sha256"]))
    assert len(rows) == 1


def test_audit_log_exists_for_every_state_transition(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("db-audit"))
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])
    wait_for_review_required(admin_api, document_id)

    events = wait_for_audit_actions(
        document_id,
        [
            "DOCUMENT_UPLOADED",
            "DOCUMENT_QUEUED",
            "EXTRACTION_STARTED",
            "EXTRACTION_COMPLETED",
            "VALIDATION_COMPLETED",
        ],
    )

    assert [event["created_at"] for event in events] == sorted(
        event["created_at"] for event in events
    )


def test_pii_fields_are_stored_and_exposed_according_to_policy(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("db-pii"))
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])
    api_document = wait_for_review_required(admin_api, document_id)

    fields = extracted_fields_for_document(document_id)
    assert fields["ssn"]["is_pii"] is True
    assert fields["ssn"]["value"] == fixture.fields["ssn"]

    api_ssn = next(field for field in api_document["extracted_fields"] if field["field_name"] == "ssn")
    assert api_ssn["display_value"] != fixture.fields["ssn"]

    events = audit_events_for_document(document_id)
    assert_no_pii_in_audit(events)


def test_rejected_documents_preserve_failure_reason(admin_api: ApiClient) -> None:
    fields = dict(DEFAULT_FIELDS["LOAN"])
    fields.pop("ssn")
    fixture = document_fixture(
        unique_suffix=correlation_id("db-failure-reason"),
        fields=fields,
    )
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])

    document = wait_for_review_required(admin_api, document_id)
    row = get_document(document_id)
    results = validation_results_for_document(document_id)

    assert document["status"] == "REJECTED"
    assert row is not None
    assert row["rejection_reason"]
    assert any(result["status"] == "FAIL" and result["is_blocking"] for result in results)
