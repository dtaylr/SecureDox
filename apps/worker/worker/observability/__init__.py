"""Worker-side instrumentation.

The worker has no HTTP surface of its own, so it cannot be scraped the way the
API is. `serve_metrics` starts a minimal listener whose only job is to answer a
Prometheus scrape — deliberately not a web framework, because an extra HTTP
stack in a queue consumer is attack surface with no user.
"""

from __future__ import annotations

from .server import serve_metrics

__all__ = ["serve_metrics"]
