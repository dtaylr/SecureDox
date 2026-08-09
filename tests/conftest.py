from __future__ import annotations

import pytest

from tests.helpers.api_client import ApiClient
from tests.helpers.user_factory import test_user


@pytest.fixture(scope="session")
def api_client() -> ApiClient:
    client = ApiClient()
    if not client.health():
        pytest.skip("SecureDox API is not running; start the local stack with make up.")
    return client


@pytest.fixture
def admin_api(api_client: ApiClient) -> ApiClient:
    api_client.login(test_user("admin"))
    return api_client
