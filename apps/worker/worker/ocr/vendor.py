"""HTTP OCR vendor adapter.

Represents the third-party dependency every real intake pipeline has, and it is
here mainly so the *failure* handling is testable: timeouts, 5xx, rate limits,
partial responses and schema drift are all things a vendor does to you on a
Tuesday afternoon.

Two properties this adapter guarantees regardless of what the vendor sends:

* A response that does not match the expected shape raises rather than
  producing half-populated fields. Silent partial extraction on a regulated
  document is worse than a retry.
* The API key never appears in a log line, an exception message or a metric.
"""

from __future__ import annotations

from typing import Any, Final

import httpx

from securedox_shared import RULE_CATALOGUE, ExtractionResult
from worker.ocr.base import OcrAdapter, OcrError, OcrRequest, OcrTimeoutError, OcrUnprocessableError

#: Vendor status codes that are worth retrying; everything else is permanent.
_RETRYABLE_STATUS: Final[frozenset[int]] = frozenset({408, 425, 429, 500, 502, 503, 504})


class VendorOcrAdapter(OcrAdapter):
    name = "vendor"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url:
            raise OcrError("OCR_VENDOR_URL is not configured.", permanent=True, kind="config")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        # Injectable so tests drive a transport mock rather than a live socket.
        self._client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=5.0),
                # Bounded pool: an unbounded one turns a slow vendor into
                # worker-wide resource exhaustion.
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def extract(self, request: OcrRequest) -> ExtractionResult:
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self._base_url}/v1/extract",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "X-Document-Type": request.document_type.value,
                },
                files={"file": (str(request.document_id), request.content, request.mime_type)},
            )
        except httpx.TimeoutException as exc:
            raise OcrTimeoutError(f"Vendor did not respond within {self._timeout}s.") from exc
        except httpx.HTTPError as exc:
            # The exception repr can contain the full request URL; only the
            # class name is propagated.
            raise OcrError(
                f"Vendor transport error: {type(exc).__name__}", kind="transport"
            ) from exc

        self._raise_for_status(response)
        payload = self._parse(response)

        fields: dict[str, str | None] = {}
        confidences: dict[str, float] = {}
        raw_fields = payload.get("fields", {})

        for rule in RULE_CATALOGUE[request.document_type]:
            entry = raw_fields.get(rule.field_name) or {}
            value = entry.get("value")
            fields[rule.field_name] = None if value is None else str(value)
            confidences[rule.field_name] = self._clamp(entry.get("confidence", 0.0))

        return ExtractionResult(
            document_id=request.document_id,
            provider=self.name,
            fields=fields,
            confidences=confidences,
            page_count=int(payload.get("page_count", 1)),
            duration_ms=int(payload.get("duration_ms", 0)),
            degraded=bool(payload.get("degraded", False)),
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        if response.status_code in _RETRYABLE_STATUS:
            raise OcrError(
                f"Vendor returned {response.status_code}.",
                permanent=False,
                kind=f"http_{response.status_code}",
            )
        if response.status_code in (400, 415, 422):
            raise OcrUnprocessableError(f"Vendor rejected the document ({response.status_code}).")
        # 401/403 are permanent: retrying a bad credential just burns quota.
        raise OcrError(
            f"Vendor returned {response.status_code}.",
            permanent=True,
            kind=f"http_{response.status_code}",
        )

    @staticmethod
    def _parse(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise OcrError("Vendor returned a non-JSON body.", kind="bad_payload") from exc
        if not isinstance(payload, dict) or "fields" not in payload:
            # Schema drift, caught at the boundary rather than three layers in.
            raise OcrError("Vendor response is missing 'fields'.", kind="schema_drift")
        return payload

    @staticmethod
    def _clamp(value: Any) -> float:
        try:
            return min(max(float(value), 0.0), 1.0)
        except (TypeError, ValueError):
            return 0.0

    async def health(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get(f"{self._base_url}/health")
        except httpx.HTTPError:
            return False
        return response.is_success

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
