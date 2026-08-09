from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_report(name: str, payload: dict[str, Any]) -> Path:
    report_dir = Path("tests/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path
