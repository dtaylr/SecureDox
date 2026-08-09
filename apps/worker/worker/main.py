"""Worker entrypoint: the consumer loop.

Delivery is at-least-once, so `DocumentProcessor` is written to be idempotent
and this loop is free to redeliver. The alternative — at-most-once — would mean
a crashed worker silently drops a regulated document, which is not a trade this
domain permits.

Failure handling, in order of preference:

1. **Transient** (vendor timeout, redis blip) → requeue with an incremented
   attempt count and a backoff delay.
2. **Retries exhausted** → dead-letter queue, where an operator can inspect and
   replay. Never dropped.
3. **Unparseable message** → dead-letter immediately. A poison message that
   keeps being requeued starves the queue of real work.

Shutdown drains: on SIGTERM the loop stops accepting new jobs and finishes the
one in flight, because a document killed mid-extraction has to be reprocessed
from the start.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from pydantic import ValidationError as PydanticValidationError
from redis.asyncio import Redis

from app.core.logging import (
    configure_logging,
    correlation_id_ctx,
    document_id_ctx,
    error_code_ctx,
    event_type_ctx,
    get_logger,
    job_id_ctx,
    latency_ms_ctx,
    status_ctx,
    tenant_id_ctx,
)
from app.db.session import dispose_engine, get_sessionmaker
from app.services.storage import build_storage
from securedox_observability import (
    configure_tracing,
    metrics,
)
from securedox_shared import IntakeJob
from worker.observability import serve_metrics
from worker.ocr import OcrError, build_adapter
from worker.processor import DocumentProcessor
from worker.rules import RuleRunner
from worker.settings import WorkerSettings, get_worker_settings

logger = get_logger(__name__)

#: Exponential backoff, capped. Index by attempt number.
_BACKOFF_SECONDS = (1, 4, 15, 60, 120)


class Worker:
    def __init__(self, settings: WorkerSettings) -> None:
        self._settings = settings
        self._redis = Redis.from_url(str(settings.redis_url), decode_responses=True)
        self._processor = DocumentProcessor(
            storage=build_storage(settings.storage_backend, settings.storage_local_path),
            ocr=build_adapter(
                settings.ocr_provider,
                vendor_url=settings.ocr_vendor_url,
                vendor_api_key=settings.ocr_vendor_api_key,
                timeout_seconds=settings.ocr_timeout_seconds,
                degradation_rate=settings.ocr_degradation_rate,
            ),
            rules=RuleRunner(confidence_threshold=settings.ocr_confidence_threshold),
        )
        self._stopping = asyncio.Event()
        self._sessionmaker = get_sessionmaker()

    def request_stop(self) -> None:
        """Signal handler: stop after the current job, do not interrupt it."""
        if not self._stopping.is_set():
            logger.info("shutdown_requested")
            self._stopping.set()

    async def run(self) -> None:
        """Consume until asked to stop, with `worker_concurrency` slots."""
        logger.info(
            "worker_started",
            queue=self._settings.queue_name,
            concurrency=self._settings.worker_concurrency,
            ocr_provider=self._settings.ocr_provider,
        )
        consumers = [
            asyncio.create_task(self._consume(slot), name=f"consumer-{slot}")
            for slot in range(self._settings.worker_concurrency)
        ]
        try:
            await asyncio.gather(*consumers)
        finally:
            await self._redis.aclose()
            await dispose_engine()
            logger.info("worker_stopped")

    async def _consume(self, slot: int) -> None:
        while not self._stopping.is_set():
            raw = await self._pop()
            if raw is None:
                continue

            job = await self._parse(raw)
            if job is None:
                continue

            token = correlation_id_ctx.set(job.correlation_id)
            tenant_token = tenant_id_ctx.set(job.tenant_id)
            document_token = document_id_ctx.set(str(job.document_id))
            job_token = job_id_ctx.set(f"{job.document_id}:{job.attempt}")
            event_token = event_type_ctx.set("document_job")
            status_token = status_ctx.set(None)
            latency_token = latency_ms_ctx.set(None)
            error_token = error_code_ctx.set(None)
            try:
                await self._handle(job)
            finally:
                correlation_id_ctx.reset(token)
                tenant_id_ctx.reset(tenant_token)
                document_id_ctx.reset(document_token)
                job_id_ctx.reset(job_token)
                event_type_ctx.reset(event_token)
                status_ctx.reset(status_token)
                latency_ms_ctx.reset(latency_token)
                error_code_ctx.reset(error_token)
        logger.debug("consumer_exited", slot=slot)

    async def _pop(self) -> str | None:
        """Blocking pop with a bounded timeout so shutdown stays responsive."""
        try:
            result = await self._redis.blpop(  # type: ignore[misc]
                [self._settings.queue_name], timeout=self._settings.poll_timeout_seconds
            )
        except Exception as exc:
            logger.warning("queue_unavailable", error_type=type(exc).__name__)
            await asyncio.sleep(2)
            return None
        # `blpop` returns (queue_name, payload) or None on timeout.
        return result[1] if result else None

    async def _parse(self, raw: str) -> IntakeJob | None:
        try:
            return IntakeJob.model_validate_json(raw)
        except PydanticValidationError as exc:
            # Contract violation from the producer. Retrying cannot fix a
            # message that will never parse, so it goes straight to the DLQ.
            logger.error("poison_message", error_count=exc.error_count())
            await self._dead_letter(raw, reason="unparseable")
            return None

    async def _handle(self, job: IntakeJob) -> None:
        try:
            async with self._sessionmaker() as session:
                outcome = await self._processor.process(session, job)
            logger.info(
                "job_complete",
                document_id=str(job.document_id),
                status=outcome.status.value,
                duration_seconds=round(outcome.duration_seconds, 3),
                latency_ms=round(outcome.duration_seconds * 1000, 3),
            )
            status_ctx.set(outcome.status.value)
            latency_ms_ctx.set(round(outcome.duration_seconds * 1000, 3))
        except OcrError as exc:
            error_code_ctx.set(exc.kind)
            await self._retry(job, reason=exc.kind)
        except Exception as exc:
            error_code_ctx.set(type(exc).__name__)
            logger.exception("job_failed", document_id=str(job.document_id))
            await self._retry(job, reason=type(exc).__name__)

    async def _retry(self, job: IntakeJob, *, reason: str) -> None:
        """Requeue with backoff, or dead-letter once the budget is spent."""
        if job.attempt >= self._settings.worker_max_retries:
            logger.error(
                "retries_exhausted",
                document_id=str(job.document_id),
                attempts=job.attempt,
                reason=reason,
            )
            await self._dead_letter(job.model_dump_json(), reason=reason)
            metrics.jobs_processed_total.labels(outcome="dead_lettered").inc()
            return

        delay = _BACKOFF_SECONDS[min(job.attempt - 1, len(_BACKOFF_SECONDS) - 1)]
        retried = job.model_copy(update={"attempt": job.attempt + 1})
        logger.warning(
            "job_retry_scheduled",
            document_id=str(job.document_id),
            attempt=retried.attempt,
            delay_seconds=delay,
            reason=reason,
        )
        metrics.job_retries_total.labels(reason=reason).inc()

        # Delay then requeue. Detached so the consumer takes the next job
        # instead of blocking a slot for the whole backoff window.
        asyncio.create_task(self._requeue_after(retried, delay))  # noqa: RUF006

    async def _requeue_after(self, job: IntakeJob, delay: int) -> None:
        await asyncio.sleep(delay)
        with contextlib.suppress(Exception):
            await self._redis.rpush(self._settings.queue_name, job.model_dump_json())  # type: ignore[misc]

    async def _dead_letter(self, payload: str, *, reason: str) -> None:
        """Park a message for operator inspection. Never silently dropped."""
        with contextlib.suppress(Exception):
            await self._redis.rpush(  # type: ignore[misc]
                self._settings.dead_letter_queue, payload
            )
        logger.error("dead_lettered", reason=reason)


async def _amain() -> None:
    settings = get_worker_settings()
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        service=settings.service_name,
        version=settings.service_version,
    )
    configure_tracing(service_name=settings.service_name, service_version=settings.service_version)
    serve_metrics(settings.metrics_port, enabled=settings.metrics_enabled)

    worker = Worker(settings)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_stop)

    await worker.run()


def main() -> None:
    try:
        asyncio.run(_amain())
    except KeyboardInterrupt:  # pragma: no cover - interactive use only
        pass


if __name__ == "__main__":
    main()
