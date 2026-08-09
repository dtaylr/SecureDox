from __future__ import annotations

import time
import uuid


def correlation_id(prefix: str = "pytest") -> str:
    return f"{prefix}-{int(time.time())}-{uuid.uuid4().hex[:10]}"[:64]


def assert_correlation_id(value: str | None) -> None:
    assert value is not None
    assert 8 <= len(value) <= 64
