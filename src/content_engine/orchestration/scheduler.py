"""Lightweight in-process job scheduler."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from threading import Event, Lock, Thread
import logging
import socket
import time
import uuid

from content_engine.config import RuntimeSettings
from content_engine.db.jobs import JobRepository
from content_engine.orchestration.engine import JobExecutionEngine
from content_engine.orchestration.metrics import MetricsSnapshot, RuntimeMetrics


class SchedulerState(StrEnum):
    STOPPED = "stopped"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass(frozen=True)
class SchedulerStatus:
    state: SchedulerState
    worker_id: str
    registered_handlers: tuple[str, ...]
    metrics: MetricsSnapshot


class Scheduler:
    def __init__(
        self,
        *,
        jobs: JobRepository,
        engine: JobExecutionEngine,
        metrics: RuntimeMetrics,
        settings: RuntimeSettings,
        logger: logging.Logger,
        worker_id: str | None = None,
    ) -> None:
        self.jobs = jobs
        self.engine = engine
        self.metrics = metrics
        self.settings = settings
        self.logger = logger
        self.worker_id = worker_id or f"{socket.gethostname()}-{uuid.uuid4()}"
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._futures: set[Future] = set()
        self._lock = Lock()
        self._state = SchedulerState.STOPPED

    @property
    def state(self) -> SchedulerState:
        return self._state

    def start(self) -> None:
        if self._state == SchedulerState.RUNNING:
            return
        recovered = self.jobs.recover_stale_running(
            older_than=timedelta(seconds=self.settings.stale_job_timeout_seconds),
            retry_delay=timedelta(seconds=self.settings.retry_delay_seconds),
        )
        if recovered:
            self.logger.warning("stale_jobs_recovered", extra={"component": "scheduler", "count": recovered})
        self._stop_event.clear()
        self._executor = ThreadPoolExecutor(max_workers=self.settings.worker_concurrency, thread_name_prefix="job-worker")
        self._state = SchedulerState.RUNNING
        self._thread = Thread(target=self._run_loop, name="job-scheduler", daemon=True)
        self._thread.start()
        self.logger.info(
            "scheduler_started",
            extra={
                "component": "scheduler",
                "worker_id": self.worker_id,
                "concurrency": self.settings.worker_concurrency,
            },
        )

    def stop(self, *, wait: bool = True) -> None:
        if self._state == SchedulerState.STOPPED and self._executor is None:
            return
        self._state = SchedulerState.STOPPING
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
        self._thread = None
        self._executor = None
        self._state = SchedulerState.STOPPED
        self.logger.info("scheduler_stopped", extra={"component": "scheduler", "worker_id": self.worker_id})

    def status(self) -> SchedulerStatus:
        queue = self.jobs.stats()
        return SchedulerStatus(
            state=self._state,
            worker_id=self.worker_id,
            registered_handlers=self.engine.handlers.registered_types(),
            metrics=self.metrics.snapshot(
                queue_pending=queue.pending,
                queue_retrying=queue.retrying,
                queue_running=queue.running,
            ),
        )

    def tick(self) -> int:
        dispatched = 0
        self._clear_finished_futures()
        while self._available_slots() > 0:
            job = self.jobs.claim_next(worker_id=self.worker_id)
            if job is None:
                break
            self._submit(job)
            dispatched += 1
        return dispatched

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            dispatched = self.tick()
            if dispatched:
                self.logger.info("jobs_dispatched", extra={"component": "scheduler", "count": dispatched})
            self._stop_event.wait(self.settings.scheduler_poll_interval_seconds)

    def _submit(self, job) -> None:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.settings.worker_concurrency, thread_name_prefix="job-worker")
        future = self._executor.submit(self.engine.execute, job)
        with self._lock:
            self._futures.add(future)

    def _available_slots(self) -> int:
        with self._lock:
            active = len(self._futures)
        return max(self.settings.worker_concurrency - active, 0)

    def _clear_finished_futures(self) -> None:
        with self._lock:
            done = {future for future in self._futures if future.done()}
            self._futures -= done
        for future in done:
            try:
                future.result()
            except Exception:
                self.logger.exception("scheduler_future_failed", extra={"component": "scheduler"})
