"""Generic job execution engine."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any

from content_engine.db.jobs import JobRepository
from content_engine.domain import Job, JobStatus
from content_engine.orchestration.metrics import RuntimeMetrics
from content_engine.orchestration.retry import RetryPolicy


@dataclass(frozen=True)
class JobResult:
    success: bool
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


JobHandler = Callable[[Job], JobResult | None]


class JobHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def register(self, job_type: str, handler: JobHandler) -> None:
        normalized = _normalize_job_type(job_type)
        if normalized in self._handlers:
            raise ValueError(f"Handler already registered for job type: {normalized}")
        self._handlers[normalized] = handler

    def get(self, job_type: str) -> JobHandler | None:
        return self._handlers.get(_normalize_job_type(job_type))

    def registered_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


class JobExecutionEngine:
    def __init__(
        self,
        *,
        jobs: JobRepository,
        handlers: JobHandlerRegistry,
        retry_policy: RetryPolicy,
        metrics: RuntimeMetrics,
        logger: logging.Logger,
    ) -> None:
        self.jobs = jobs
        self.handlers = handlers
        self.retry_policy = retry_policy
        self.metrics = metrics
        self.logger = logger

    def execute(self, job: Job) -> Job:
        started = time.monotonic()
        self.metrics.record_started()
        self.logger.info(
            "job_execution_started",
            extra={"component": "orchestration", "job_id": job.id, "job_type": job.job_type},
        )
        try:
            handler = self.handlers.get(job.job_type)
            if handler is None:
                raise UnregisteredJobTypeError(f"No handler registered for job type: {job.job_type}")
            result = handler(job)
            if result is not None and not result.success:
                raise JobHandlerError(result.message or "Job handler reported failure")
            completed = self.jobs.mark_completed(job.id)
            self.metrics.record_completed(time.monotonic() - started)
            self.logger.info(
                "job_execution_completed",
                extra={
                    "component": "orchestration",
                    "job_id": job.id,
                    "job_type": job.job_type,
                    "result_message": result.message if result else "",
                    "result_metadata": result.metadata if result else {},
                },
            )
            return completed
        except Exception as exc:
            return self._handle_failure(job, exc, time.monotonic() - started)

    def _handle_failure(self, job: Job, exc: Exception, duration_seconds: float) -> Job:
        current = self.jobs.get(job.id) or job
        error = str(exc) or exc.__class__.__name__
        now = datetime.now(timezone.utc)
        decision = self.retry_policy.decide(current, now=now)
        if decision.should_retry and not isinstance(exc, UnregisteredJobTypeError):
            retried = self.jobs.mark_retrying(current.id, error=error, run_after=decision.run_after or now, now=now)
            self.metrics.record_retried(duration_seconds)
            self.logger.warning(
                "job_execution_retrying",
                extra={
                    "component": "orchestration",
                    "job_id": current.id,
                    "job_type": current.job_type,
                    "attempts": current.attempts,
                    "error": error,
                    "run_after": decision.run_after,
                },
            )
            return retried
        failed = self.jobs.mark_failed(current.id, error=error, now=now)
        self.metrics.record_failed(duration_seconds)
        self.logger.error(
            "job_execution_failed",
            extra={
                "component": "orchestration",
                "job_id": current.id,
                "job_type": current.job_type,
                "attempts": current.attempts,
                "status": JobStatus.FAILED.value,
                "error": error,
            },
        )
        return failed


class JobHandlerError(RuntimeError):
    """Raised when a handler returns an unsuccessful result."""


class UnregisteredJobTypeError(RuntimeError):
    """Raised when a claimed job has no registered handler."""


def _normalize_job_type(job_type: str) -> str:
    normalized = job_type.strip().upper()
    if not normalized:
        raise ValueError("job_type cannot be empty")
    return normalized
