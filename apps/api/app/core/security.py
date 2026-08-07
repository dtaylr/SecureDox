"""Authentication primitives.

A deliberately small HS256 JWT shim: this repo demonstrates *testing* a
regulated workflow, not an identity provider, so the token format is minimal
and the signing key comes from the environment. Two properties still matter
and are enforced here because `tests/security/authz` asserts them:

1. The tenant claim in the token is the only source of tenant identity. A
   `tenant_id` in a path, query or body is never trusted.
2. `alg` is pinned. Accepting the token's own `alg` header is the classic
   `alg: none` / HS-vs-RS confusion bypass.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Final

import jwt

from app.core.config import get_settings
from app.core.errors import UnauthorizedError

#: Roles are coarse on purpose — the interesting authz surface in this domain
#: is the tenant boundary, not a deep permission tree.
ROLE_ADMIN: Final = "admin"
ROLE_REVIEWER: Final = "reviewer"
ROLE_UPLOADER: Final = "uploader"
ROLE_SERVICE: Final = "service"

_ALL_ROLES: Final[frozenset[str]] = frozenset(
    {ROLE_ADMIN, ROLE_REVIEWER, ROLE_UPLOADER, ROLE_SERVICE}
)


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller, as derived *only* from a verified token."""

    subject: str
    tenant_id: str
    roles: frozenset[str]

    def has_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))

    @property
    def is_admin(self) -> bool:
        return ROLE_ADMIN in self.roles

    def owns(self, tenant_id: str) -> bool:
        """Admins are still tenant-scoped: there is no cross-tenant super-user."""
        return self.tenant_id == tenant_id


def issue_token(
    *,
    subject: str,
    tenant_id: str,
    roles: set[str] | frozenset[str],
    ttl_seconds: int | None = None,
) -> str:
    """Mint a token. Used by the demo login route and by test fixtures."""
    settings = get_settings()
    unknown = set(roles) - _ALL_ROLES
    if unknown:
        raise ValueError(f"unknown roles: {sorted(unknown)}")

    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "roles": sorted(roles),
        "iss": settings.auth_jwt_issuer,
        "iat": now,
        "nbf": now,
        "exp": now + (ttl_seconds or settings.auth_token_ttl_seconds),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm=settings.auth_jwt_algorithm)


def decode_token(token: str) -> Principal:
    """Verify a token and project it onto a `Principal`.

    Every failure mode collapses to one generic 401: a caller must not learn
    whether a token was expired, wrongly signed or malformed.
    """
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.auth_jwt_secret,
            # A list with exactly one entry — never `claims["alg"]`.
            algorithms=[settings.auth_jwt_algorithm],
            issuer=settings.auth_jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss"], "verify_exp": True},
        )
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc

    tenant_id = claims.get("tenant_id")
    subject = claims.get("sub")
    if not isinstance(tenant_id, str) or not tenant_id or not isinstance(subject, str):
        raise UnauthorizedError("Token is missing a tenant claim.")

    raw_roles = claims.get("roles", [])
    roles = frozenset(r for r in raw_roles if isinstance(r, str) and r in _ALL_ROLES)
    if not roles:
        raise UnauthorizedError("Token carries no usable role.")

    return Principal(subject=subject, tenant_id=tenant_id, roles=roles)


def parse_bearer(header_value: str | None) -> str:
    """Pull the credential out of an `Authorization` header."""
    if not header_value:
        raise UnauthorizedError()
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError()
    return token.strip()


def checksum(data: bytes) -> str:
    """SHA-256 of an uploaded file: dedupe key and integrity check."""
    return hashlib.sha256(data).hexdigest()


def constant_time_equals(left: str, right: str) -> bool:
    """For comparing secrets (API keys, checksums) without a timing oracle."""
    return hmac.compare_digest(left, right)
