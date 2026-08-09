from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

from tests.helpers.document_factory import DocumentFixture
from tests.helpers.user_factory import TestUser


@dataclass(slots=True)
class ApiClient:
    base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    token: str | None = None

    def health(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def login(self, user: TestUser) -> str:
        response = httpx.post(
            f"{self.base_url}/api/v1/auth/login",
            json={
                "username": user.username,
                "password": user.password,
                "tenant_id": user.tenant_id,
            },
            timeout=10,
        )
        response.raise_for_status()
        self.token = str(response.json()["access_token"])
        return self.token

    def upload_document(
        self, fixture: DocumentFixture, *, correlation_id: str | None = None
    ) -> dict[str, Any]:
        headers = self._headers(correlation_id=correlation_id)
        response = httpx.post(
            f"{self.base_url}/api/v1/documents",
            data={"document_type": fixture.document_type},
            files={"file": (fixture.filename, fixture.content, fixture.mime_type)},
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        return dict(response.json())

    def get_document(self, document_id: str) -> dict[str, Any]:
        response = httpx.get(
            f"{self.base_url}/api/v1/documents/{document_id}",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return dict(response.json())

    def get_document_response(self, document_id: str) -> httpx.Response:
        return httpx.get(
            f"{self.base_url}/api/v1/documents/{document_id}",
            headers=self._headers(),
            timeout=10,
        )

    def review_document_response(
        self,
        document_id: str,
        *,
        note: str,
        corrections: list[dict[str, str]] | None = None,
    ) -> httpx.Response:
        return httpx.patch(
            f"{self.base_url}/api/v1/documents/{document_id}/review",
            json={"note": note, "corrections": corrections or []},
            headers=self._headers(),
            timeout=10,
        )

    def review_document(
        self,
        document_id: str,
        *,
        note: str = "Reviewed by pytest",
        corrections: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        response = self.review_document_response(
            document_id,
            note=note,
            corrections=corrections,
        )
        response.raise_for_status()
        return dict(response.json())

    def submit_document(self, document_id: str, note: str = "pytest smoke review") -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/v1/documents/{document_id}/submit",
            json={"note": note},
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return dict(response.json())

    def submit_document_response(
        self, document_id: str, note: str = "pytest smoke review"
    ) -> httpx.Response:
        return httpx.post(
            f"{self.base_url}/api/v1/documents/{document_id}/submit",
            json={"note": note},
            headers=self._headers(),
            timeout=10,
        )

    def list_audit_logs(
        self, *, document_id: str | None = None, action: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if document_id:
            params["document_id"] = document_id
        if action:
            params["action"] = action
        response = httpx.get(
            f"{self.base_url}/api/v1/audit-logs",
            params=params,
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return dict(response.json())

    def unauthenticated_upload(self, fixture: DocumentFixture) -> httpx.Response:
        return httpx.post(
            f"{self.base_url}/api/v1/documents",
            data={"document_type": fixture.document_type},
            files={"file": (fixture.filename, fixture.content, fixture.mime_type)},
            timeout=20,
        )

    def upload_document_response(self, fixture: DocumentFixture) -> httpx.Response:
        return httpx.post(
            f"{self.base_url}/api/v1/documents",
            data={"document_type": fixture.document_type},
            files={"file": (fixture.filename, fixture.content, fixture.mime_type)},
            headers=self._headers(),
            timeout=20,
        )

    def _headers(self, *, correlation_id: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers
