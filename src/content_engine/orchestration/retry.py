"""Retry policy for failed jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from content_engine.config import RuntimeSettings
from content_engine.domain import Job


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    run_after: datetime | None
    reason: str


@dataclass(frozen=True)
class RetryPolicy:
    base_delay: timedelta
    backoff_multiplier: float
    max_delay: timedelta

    @classmethod
    def from_settings(cls, settings: RuntimeSettings) -> "RetryPolicy":
        return cls(
            base_delay=timedelta(seconds=settings.retry_delay_seconds),
            backoff_multiplier=settings.retry_backoff_multiplier,
            max_delay=timedelta(seconds=settings.retry_max_delay_seconds),
        )

    def decide(self, job: Job, *, now: datetime) -> RetryDecision:
        if job.attempts >= job.max_attempts:
            return RetryDecision(False, None, "maximum attempts reached")
        delay = self.delay_for_attempt(job.attempts)
        return RetryDecision(True, now + delay, f"retry after {delay.total_seconds():.0f}s")

    def delay_for_attempt(self, attempts: int) -> timedelta:
        exponent = max(attempts - 1, 0)
        seconds = self.base_delay.total_seconds() * (self.backoff_multiplier**exponent)
        return min(timedelta(seconds=seconds), self.max_delay)

