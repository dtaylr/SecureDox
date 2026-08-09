from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["admin", "reviewer", "uploader"]


@dataclass(frozen=True, slots=True)
class TestUser:
    username: Role
    password: str = "securedox-demo"
    tenant_id: str = "acme-lending"


def test_user(role: Role = "admin", tenant_id: str = "acme-lending") -> TestUser:
    return TestUser(username=role, tenant_id=tenant_id)
