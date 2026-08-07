"""Demo authentication.

Explicitly a shim, not an identity provider: it exists so the web app, the
mobile app and the test suites have a way to obtain a scoped token. Real
deployments front this service with an OIDC provider and this router is not
mounted — `settings.is_production` refuses to serve it.

The credential check is deliberately constant-time and gives one generic error
for both "no such user" and "wrong password", because a username-enumeration
oracle is the finding a pentest would open against a login route.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import PrincipalDep, SettingsDep
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import (
    ROLE_ADMIN,
    ROLE_REVIEWER,
    ROLE_UPLOADER,
    constant_time_equals,
    issue_token,
)
from app.schemas.auth import LoginRequest, PrincipalOut, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

#: Seeded demo users. Mirrors `app/db/seed.py`; the password is shared and
#: non-secret by design, and gitleaks allowlists this constant.
_DEMO_USERS: dict[str, tuple[str, frozenset[str]]] = {
    "admin": ("securedox-demo", frozenset({ROLE_ADMIN})),
    "reviewer": ("securedox-demo", frozenset({ROLE_REVIEWER})),
    "uploader": ("securedox-demo", frozenset({ROLE_UPLOADER})),
}


@router.post("/login", response_model=TokenResponse, summary="Exchange demo credentials")
async def login(payload: LoginRequest, settings: SettingsDep) -> TokenResponse:
    if settings.is_production:
        raise ForbiddenError("The demo login route is disabled in production.")

    record = _DEMO_USERS.get(payload.username)
    # Compare against a dummy when the user is unknown so both branches cost
    # the same — the timing difference is the enumeration oracle.
    expected = record[0] if record else "\x00" * len("securedox-demo")
    password_ok = constant_time_equals(payload.password, expected)

    if record is None or not password_ok:
        raise UnauthorizedError("Invalid credentials.")

    token = issue_token(
        subject=payload.username,
        tenant_id=payload.tenant_id,
        roles=record[1],
    )
    return TokenResponse(access_token=token, expires_in=settings.auth_token_ttl_seconds)


@router.get("/me", response_model=PrincipalOut, summary="Describe the current caller")
async def me(principal: PrincipalDep) -> PrincipalOut:
    """Lets a client render role-gated UI without decoding the token itself."""
    return PrincipalOut(
        subject=principal.subject,
        tenant_id=principal.tenant_id,
        roles=sorted(principal.roles),
    )
