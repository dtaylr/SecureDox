"""Auth request/response models for the demo login shim."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=128)
    #: Never logged: `securedox_observability.redaction` treats "password" as a
    #: sensitive key, so even an exception repr of this model is safe.
    password: str = Field(min_length=1, max_length=256)
    tenant_id: str = Field(min_length=2, max_length=64)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth scheme name, not a credential
    expires_in: int


class PrincipalOut(BaseModel):
    """Echoed by GET /auth/me so a client can render role-gated UI."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    tenant_id: str
    roles: list[str]
