"""In-memory runtime metrics for the orchestration engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock


@dataclass(frozen=True)
class MetricsSnapshot:
    jobs_completed: int
    jobs_failed: int
    jobs_retried: int
    jobs_started: int
    average_execution_time_seconds: float
    worker_uptime_seconds: float
    queue_pending: int
    queue_retrying: int
    queue_running: int


@dataclass
class RuntimeMetrics:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _jobs_completed: int = 0
    _jobs_failed: int = 0
    _jobs_retried: int = 0
    _jobs_started: int = 0
    _total_execution_seconds: float = 0.0
    _lock: Lock = field(default_factory=Lock)

    def record_started(self) -> None:
        with self._lock:
            self._jobs_started += 1

    def record_completed(self, duration_seconds: float) -> None:
        with self._lock:
            self._jobs_completed += 1
            self._total_execution_seconds += duration_seconds

    def record_failed(self, duration_seconds: float) -> None:
        with self._lock:
            self._jobs_failed += 1
            self._total_execution_seconds += duration_seconds

    def record_retried(self, duration_seconds: float) -> None:
        with self._lock:
            self._jobs_retried += 1
            self._total_execution_seconds += duration_seconds

    def snapshot(self, *, queue_pending: int = 0, queue_retrying: int = 0, queue_running: int = 0) -> MetricsSnapshot:
        with self._lock:
            finished = self._jobs_completed + self._jobs_failed + self._jobs_retried
            average = self._total_execution_seconds / finished if finished else 0.0
            uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
            return MetricsSnapshot(
                jobs_completed=self._jobs_completed,
                jobs_failed=self._jobs_failed,
                jobs_retried=self._jobs_retried,
                jobs_started=self._jobs_started,
                average_execution_time_seconds=average,
                worker_uptime_seconds=uptime,
                queue_pending=queue_pending,
                queue_retrying=queue_retrying,
                queue_running=queue_running,
            )

