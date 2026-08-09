"""Version 1 of the HTTP API.

Versioning is in the path (`/api/v1`) rather than a header so a browser, a
mobile client and a curl one-liner in a runbook all pin the same way. A v2
would be a sibling package; v1 handlers are never edited in a breaking way.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, auth, documents, health

router = APIRouter()

# Probes live at the root, outside the version prefix: an orchestrator's probe
# configuration must not have to change when the API version does.
root_router = APIRouter()
root_router.include_router(health.router)

router.include_router(auth.router)
router.include_router(documents.router)
router.include_router(admin.router)

__all__ = ["root_router", "router"]
