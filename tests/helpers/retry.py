from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def wait_until(
    operation: Callable[[], T],
    predicate: Callable[[T], bool],
    *,
    timeout_seconds: float = 30,
    interval_seconds: float = 0.5,
    description: str = "condition",
) -> T:
    deadline = time.monotonic() + timeout_seconds
    last_value: T | None = None
    while time.monotonic() < deadline:
        last_value = operation()
        if predicate(last_value):
            return last_value
        time.sleep(interval_seconds)
    raise AssertionError(f"Timed out waiting for {description}; last value was {last_value!r}")
