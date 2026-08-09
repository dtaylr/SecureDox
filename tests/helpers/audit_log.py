from __future__ import annotations

import re
from typing import Any

from tests.helpers.db_client import audit_events_for_document
from tests.helpers.retry import wait_until


def wait_for_audit_actions(document_id: str, expected_actions: list[str]) -> list[dict[str, Any]]:
    return wait_until(
        lambda: audit_events_for_document(document_id),
        lambda events: all(
            expected in {str(event["action"]) for event in events} for expected in expected_actions
        ),
        description=f"audit actions {expected_actions}",
    )


def assert_audit_actions(events: list[dict[str, Any]], expected_actions: list[str]) -> None:
    actual = {str(event["action"]) for event in events}
    missing = [action for action in expected_actions if action not in actual]
    assert not missing, f"Missing audit actions: {missing}"


def assert_no_pii_in_audit(events: list[dict[str, Any]]) -> None:
    for event in events:
        assert not re.search(r"\d{3}-\d{2}-\d{4}", str(event.get("detail", {})))
