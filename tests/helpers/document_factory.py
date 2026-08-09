from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Literal

DocumentType = Literal["LOAN", "INSURANCE", "MEDICAL", "ONBOARDING"]


@dataclass(frozen=True, slots=True)
class DocumentFixture:
    document_type: DocumentType
    filename: str
    mime_type: str
    content: bytes
    fields: dict[str, str | None]
    confidences: dict[str, float]


DEFAULT_FIELDS: dict[DocumentType, dict[str, str | None]] = {
    "LOAN": {
        "applicant_name": "Jordan Rivera",
        "ssn": "000-00-0000",
        "loan_amount": "$45,000.00",
        "application_date": "2026-01-15",
        "employer": "Contoso Manufacturing",
    },
    "INSURANCE": {
        "policy_number": "AB-1234567",
        "insured_name": "Sam Okafor",
        "effective_date": "2026-02-01",
        "claim_amount": "$1,250.00",
    },
    "MEDICAL": {
        "patient_mrn": "MRN1234567",
        "patient_name": "Alex Chen",
        "date_of_service": "2026-01-20",
        "provider_npi": "1234567890",
    },
    "ONBOARDING": {
        "full_name": "Priya Nair",
        "start_date": "2026-03-01",
        "email": "priya.nair@example.com",
        "id_document_number": "X1234567",
    },
}


def document_fixture(
    document_type: DocumentType = "LOAN",
    *,
    unique_suffix: str | None = None,
    fields: dict[str, str | None] | None = None,
    confidences: dict[str, float] | None = None,
    content: bytes | None = None,
    filename: str | None = None,
    mime_type: str = "application/pdf",
) -> DocumentFixture:
    selected_fields = fields or DEFAULT_FIELDS[document_type]
    selected_confidences = confidences or {field: 0.95 for field in selected_fields}
    fixture_block = json.dumps(
        {
            "fields": selected_fields,
            "confidences": selected_confidences,
        },
        separators=(",", ":"),
    )
    suffix = unique_suffix or str(time.time_ns())
    built_content = content or (
        f"%PDF-1.4\n% SecureDox pytest fixture {suffix}\n"
        f"SECUREDOX-FIXTURE:{fixture_block}\n%%EOF\n"
    ).encode()
    return DocumentFixture(
        document_type=document_type,
        filename=filename or f"pytest-{document_type.lower()}-{suffix}.pdf",
        mime_type=mime_type,
        content=built_content,
        fields=selected_fields,
        confidences=selected_confidences,
    )
