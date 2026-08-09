from __future__ import annotations

from tests.helpers.api_client import ApiClient
from tests.helpers.correlation import correlation_id
from tests.helpers.document_factory import document_fixture
from tests.helpers.user_factory import test_user
from tests.helpers.wait_for_job import wait_for_review_required


def test_post_documents_rejects_unauthenticated_user(api_client: ApiClient) -> None:
    response = api_client.unauthenticated_upload(
        document_fixture(unique_suffix=correlation_id("api-unauth"))
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_post_documents_accepts_valid_upload(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("api-upload"))

    upload = admin_api.upload_document(fixture)

    assert upload["status"] == "QUEUED"
    assert upload["document_type"] == fixture.document_type
    assert upload["id"]


def test_get_document_enforces_ownership(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("api-idor"))
    upload = admin_api.upload_document(fixture)
    wait_for_review_required(admin_api, str(upload["id"]))

    northwind = ApiClient(base_url=admin_api.base_url)
    northwind.login(test_user("admin", tenant_id="northwind-health"))
    response = northwind.get_document_response(str(upload["id"]))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_patch_document_review_validates_payload(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("api-review-validation"))
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])
    wait_for_review_required(admin_api, document_id)

    response = admin_api.review_document_response(document_id, note="no")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_post_document_submit_prevents_duplicate_submit(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("api-duplicate-submit"))
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])
    wait_for_review_required(admin_api, document_id)

    first = admin_api.submit_document_response(document_id, note="first reviewer attestation")
    assert first.status_code == 200

    second = admin_api.submit_document_response(document_id, note="second reviewer attestation")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


def test_get_audit_logs_returns_authorized_records_only(admin_api: ApiClient) -> None:
    fixture = document_fixture(unique_suffix=correlation_id("api-audit-scope"))
    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])
    wait_for_review_required(admin_api, document_id)

    acme_logs = admin_api.list_audit_logs(document_id=document_id)
    assert acme_logs["items"]
    assert {event["document_id"] for event in acme_logs["items"]} == {document_id}

    northwind = ApiClient(base_url=admin_api.base_url)
    northwind.login(test_user("admin", tenant_id="northwind-health"))
    northwind_logs = northwind.list_audit_logs(document_id=document_id)
    assert northwind_logs["items"] == []
