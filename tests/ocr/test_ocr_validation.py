from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

from tests.helpers.api_client import ApiClient
from tests.helpers.audit_log import assert_audit_actions, wait_for_audit_actions
from tests.helpers.correlation import correlation_id
from tests.helpers.db_client import extracted_fields_for_document
from tests.helpers.document_factory import DocumentFixture
from tests.helpers.reporting import write_report
from tests.helpers.wait_for_job import wait_for_review_required

ROOT = Path(__file__).resolve().parents[2]
TEST_DOCUMENTS = ROOT / "test-documents"
EXPECTED = ROOT / "tests" / "fixtures" / "ocr"
OCR_LATENCY_THRESHOLD_MS = 5_000


def test_clean_document_extracts_required_fields(admin_api: ApiClient) -> None:
    fixture = _fixture_from_file(
        TEST_DOCUMENTS / "clean" / "loan-application.pdf",
        document_type="LOAN",
        unique=True,
    )
    expected = _expected("loan-application.expected.json")

    upload = admin_api.upload_document(fixture)
    document = wait_for_review_required(admin_api, str(upload["id"]))

    assert document["status"] == expected["expected_status"]
    assert document["ocr_provider"] == expected["provider"]
    actual_fields = {field["field_name"]: field for field in document["extracted_fields"]}
    for field_name, value in expected["fields"].items():
        assert actual_fields[field_name]["value"] == value
        assert actual_fields[field_name]["confidence"] >= expected["min_confidence"]


def test_low_confidence_document_routes_to_manual_review(admin_api: ApiClient) -> None:
    fixture = _fixture_from_file(
        TEST_DOCUMENTS / "low-contrast" / "loan-application-low-contrast.pdf",
        document_type="LOAN",
        unique=True,
    )

    upload = admin_api.upload_document(fixture)
    document = wait_for_review_required(admin_api, str(upload["id"]))

    assert document["status"] == "REVIEW_REQUIRED"
    assert document["needs_manual_review"] is True
    assert any(field["low_confidence"] for field in document["extracted_fields"])

    submitted = admin_api.submit_document(str(upload["id"]), note="Manual review fallback approved")
    assert submitted["status"] == "VALIDATED"


def test_missing_required_field_creates_validation_error(admin_api: ApiClient) -> None:
    fixture = _fixture_from_file(
        TEST_DOCUMENTS / "missing-field" / "loan-application-missing-ssn.pdf",
        document_type="LOAN",
        unique=True,
    )

    upload = admin_api.upload_document(fixture)
    document = wait_for_review_required(admin_api, str(upload["id"]))

    assert document["status"] == "REJECTED"
    failures = [result for result in document["validation_results"] if result["status"] == "FAIL"]
    assert any(result["field_name"] == "ssn" for result in failures)


def test_duplicate_document_is_rejected(admin_api: ApiClient) -> None:
    content = (TEST_DOCUMENTS / "duplicate" / "loan-application-duplicate-a.pdf").read_bytes()
    content = content.replace(b"%%EOF", f"% {correlation_id('duplicate')}\n%%EOF".encode())
    first = DocumentFixture(
        document_type="LOAN",
        filename="duplicate-a.pdf",
        mime_type="application/pdf",
        content=content,
        fields={},
        confidences={},
    )
    second = DocumentFixture(
        document_type="LOAN",
        filename="duplicate-b.pdf",
        mime_type="application/pdf",
        content=content,
        fields={},
        confidences={},
    )

    admin_api.upload_document(first)
    try:
        admin_api.upload_document(second)
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 409
        assert exc.response.json()["error"]["code"] == "DUPLICATE_DOCUMENT"
    else:  # pragma: no cover - failure branch
        raise AssertionError("Duplicate upload unexpectedly succeeded")


def test_malformed_file_is_rejected(admin_api: ApiClient) -> None:
    fixture = DocumentFixture(
        document_type="LOAN",
        filename="not-a-pdf.pdf",
        mime_type="application/pdf",
        content=(TEST_DOCUMENTS / "invalid-format" / "not-a-pdf.pdf").read_bytes(),
        fields={},
        confidences={},
    )

    response = _try_upload(admin_api, fixture)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_unsafe_file_type_is_rejected(admin_api: ApiClient) -> None:
    fixture = DocumentFixture(
        document_type="LOAN",
        filename="script.html",
        mime_type="text/html",
        content=(TEST_DOCUMENTS / "malicious" / "script.html").read_bytes(),
        fields={},
        confidences={},
    )

    response = _try_upload(admin_api, fixture)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_ocr_result_is_stored_and_audit_tracks_lifecycle(admin_api: ApiClient) -> None:
    fixture = _fixture_from_file(
        TEST_DOCUMENTS / "clean" / "medical-intake.pdf",
        document_type="MEDICAL",
        unique=True,
    )
    expected = _expected("medical-intake.expected.json")

    upload = admin_api.upload_document(fixture)
    document_id = str(upload["id"])
    document = wait_for_review_required(admin_api, document_id)
    stored = extracted_fields_for_document(document_id)

    assert document["status"] == "VALIDATED"
    for field_name, value in expected["fields"].items():
        assert stored[field_name]["value"] == value

    events = wait_for_audit_actions(
        document_id,
        ["EXTRACTION_STARTED", "EXTRACTION_COMPLETED", "VALIDATION_COMPLETED"],
    )
    assert_audit_actions(events, ["EXTRACTION_STARTED", "EXTRACTION_COMPLETED"])


def test_ocr_latency_stays_under_threshold(admin_api: ApiClient) -> None:
    fixture = _fixture_from_file(
        TEST_DOCUMENTS / "rotated" / "loan-application-rotated.pdf",
        document_type="LOAN",
        unique=True,
    )
    started = time.perf_counter()

    upload = admin_api.upload_document(fixture)
    document = wait_for_review_required(admin_api, str(upload["id"]))
    latency_ms = round((time.perf_counter() - started) * 1000)

    assert document["status"] in {"REVIEW_REQUIRED", "VALIDATED"}
    assert latency_ms <= OCR_LATENCY_THRESHOLD_MS
    write_report(
        "ocr-quality-summary",
        {
            "ocr_adapter": document["ocr_provider"],
            "ocr_fixture": fixture.filename,
            "manual_review_required": document["needs_manual_review"],
            "p95_ocr_latency_ms": latency_ms,
            "threshold_ms": OCR_LATENCY_THRESHOLD_MS,
            "status": "passed",
        },
    )


def _fixture_from_file(path: Path, *, document_type: str, unique: bool = False) -> DocumentFixture:
    content = path.read_bytes()
    if unique:
        content = content.replace(b"%%EOF", f"% {correlation_id('ocr')}\n%%EOF".encode())
    return DocumentFixture(
        document_type=document_type,  # type: ignore[arg-type]
        filename=path.name,
        mime_type="application/pdf",
        content=content,
        fields={},
        confidences={},
    )


def _try_upload(api: ApiClient, fixture: DocumentFixture) -> httpx.Response:
    return api.upload_document_response(fixture)


def _expected(filename: str) -> dict[str, Any]:
    return json.loads((EXPECTED / filename).read_text())
