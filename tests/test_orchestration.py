from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from content_engine.config import RuntimeSettings
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.domain import Job, JobStatus
from content_engine.observability import get_logger
from content_engine.orchestration import JobExecutionEngine, JobHandlerRegistry, JobResult, RetryPolicy, RuntimeMetrics, Scheduler


def build_engine(tmp_path: Path):
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    repositories = RepositoryRegistry.create(database)
    handlers = JobHandlerRegistry()
    metrics = RuntimeMetrics()
    retry_policy = RetryPolicy(
        base_delay=timedelta(seconds=1),
        backoff_multiplier=2,
        max_delay=timedelta(seconds=60),
    )
    engine = JobExecutionEngine(
        jobs=repositories.jobs,
        handlers=handlers,
        retry_policy=retry_policy,
        metrics=metrics,
        logger=get_logger("test"),
    )
    return repositories, handlers, metrics, engine


def test_worker_execution_completes_successful_job(tmp_path: Path) -> None:
    repositories, handlers, metrics, engine = build_engine(tmp_path)
    handlers.register("FETCH_TOPICS", lambda job: JobResult(success=True, message=job.id))
    job = repositories.jobs.create(job_type="FETCH_TOPICS")
    claimed = repositories.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)
    snapshot = metrics.snapshot()

    assert result.status == JobStatus.COMPLETED
    assert repositories.jobs.get(job.id).status == JobStatus.COMPLETED
    assert snapshot.jobs_completed == 1


def test_worker_execution_retries_handler_exception(tmp_path: Path) -> None:
    repositories, handlers, metrics, engine = build_engine(tmp_path)

    def failing_handler(_job: Job) -> JobResult:
        raise RuntimeError("temporary failure")

    handlers.register("FETCH_TOPICS", failing_handler)
    job = repositories.jobs.create(job_type="FETCH_TOPICS", max_attempts=2)
    claimed = repositories.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)
    snapshot = metrics.snapshot()

    assert result.status == JobStatus.RETRYING
    assert result.last_error == "temporary failure"
    assert result.run_after is not None
    assert repositories.jobs.get(job.id).status == JobStatus.RETRYING
    assert snapshot.jobs_retried == 1


def test_worker_execution_marks_permanent_failure_after_max_attempts(tmp_path: Path) -> None:
    repositories, handlers, _metrics, engine = build_engine(tmp_path)
    handlers.register("FETCH_TOPICS", lambda _job: JobResult(success=False, message="nope"))
    job = repositories.jobs.create(job_type="FETCH_TOPICS", max_attempts=1)
    claimed = repositories.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)

    assert result.status == JobStatus.FAILED
    assert repositories.jobs.get(job.id).status == JobStatus.FAILED


def test_unregistered_job_type_fails_without_retry(tmp_path: Path) -> None:
    repositories, _handlers, _metrics, engine = build_engine(tmp_path)
    job = repositories.jobs.create(job_type="UNKNOWN", max_attempts=3)
    claimed = repositories.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)

    assert result.status == JobStatus.FAILED
    assert "No handler registered" in (result.last_error or "")
    assert repositories.jobs.get(job.id).attempts == 1


def test_scheduler_dispatches_pending_jobs_without_duplicates(tmp_path: Path) -> None:
    repositories, handlers, metrics, engine = build_engine(tmp_path)
    executed: list[str] = []
    handlers.register("FETCH_TOPICS", lambda job: executed.append(job.id) or JobResult(success=True))
    first = repositories.jobs.create(job_type="FETCH_TOPICS", priority=1)
    second = repositories.jobs.create(job_type="FETCH_TOPICS", priority=2)
    scheduler = Scheduler(
        jobs=repositories.jobs,
        engine=engine,
        metrics=metrics,
        settings=RuntimeSettings(worker_concurrency=1, scheduler_poll_interval_seconds=1),
        logger=get_logger("test"),
        worker_id="scheduler-test",
    )

    assert scheduler.tick() == 1
    scheduler.stop(wait=True)
    assert scheduler.tick() == 1
    scheduler.stop(wait=True)

    assert executed == [first.id, second.id]
    assert repositories.jobs.stats().completed == 2


def test_scheduler_start_recovers_stale_jobs(tmp_path: Path) -> None:
    repositories, _handlers, metrics, engine = build_engine(tmp_path)
    now = datetime.now(timezone.utc)
    job = repositories.jobs.create(job_type="FETCH_TOPICS", max_attempts=2)
    assert repositories.jobs.claim_next(worker_id="old-worker", now=now - timedelta(hours=2)) is not None
    scheduler = Scheduler(
        jobs=repositories.jobs,
        engine=engine,
        metrics=metrics,
        settings=RuntimeSettings(
            worker_concurrency=1,
            scheduler_poll_interval_seconds=10,
            stale_job_timeout_seconds=1,
            retry_delay_seconds=1,
        ),
        logger=get_logger("test"),
        worker_id="scheduler-test",
    )

    scheduler.start()
    scheduler.stop(wait=True)

    recovered = repositories.jobs.get(job.id)
    assert recovered is not None
    assert recovered.status == JobStatus.RETRYING

