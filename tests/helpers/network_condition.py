from __future__ import annotations

import socket


def can_connect(host: str = "localhost", port: int = 8000, timeout_seconds: float = 2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False
