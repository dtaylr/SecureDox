from __future__ import annotations

from tests.helpers.api_client import ApiClient
from tests.helpers.document_factory import document_fixture


def test_unauthenticated_user_cannot_upload(api_client: ApiClient) -> None:
    response = api_client.unauthenticated_upload(document_fixture())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
