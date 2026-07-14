from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.domain import JobStatus


def build_repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def test_job_creation_and_persistence(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)

    job = repositories.jobs.create(job_type="FETCH_TOPICS", payload={"source": "test"}, priority=10)
    persisted = repositories.jobs.get(job.id)

    assert persisted is not None
    assert persisted.job_type == "FETCH_TOPICS"
    assert persisted.payload == {"source": "test"}
    assert persisted.status == JobStatus.PENDING


def test_queue_ordering_respects_schedule_priority_and_creation(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    now = datetime.now(timezone.utc)
    future = now + timedelta(hours=1)

    later = repositories.jobs.create(job_type="LATER", priority=1, run_after=future)
    low_priority = repositories.jobs.create(job_type="LOW", priority=50)
    high_priority = repositories.jobs.create(job_type="HIGH", priority=5)

    claimed = repositories.jobs.claim_next(worker_id="test-worker", now=now)
    second = repositories.jobs.claim_next(worker_id="test-worker", now=now)
    third = repositories.jobs.claim_next(worker_id="test-worker", now=now)

    assert claimed is not None
    assert second is not None
    assert claimed.id == high_priority.id
    assert second.id == low_priority.id
    assert third is None
    assert repositories.jobs.get(later.id).status == JobStatus.PENDING


def test_claimed_jobs_are_persisted_as_running(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    job = repositories.jobs.create(job_type="FETCH_TOPICS")

    claimed = repositories.jobs.claim_next(worker_id="worker-a")

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.RUNNING
    assert claimed.attempts == 1
    assert claimed.locked_by == "worker-a"


def test_stale_running_jobs_recover_to_retrying(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    now = datetime.now(timezone.utc)
    job = repositories.jobs.create(job_type="FETCH_TOPICS", max_attempts=3)
    claimed = repositories.jobs.claim_next(worker_id="worker-a", now=now - timedelta(hours=2))
    assert claimed is not None

    recovered = repositories.jobs.recover_stale_running(
        older_than=timedelta(hours=1),
        retry_delay=timedelta(seconds=30),
        now=now,
    )
    persisted = repositories.jobs.get(job.id)

    assert recovered == 1
    assert persisted is not None
    assert persisted.status == JobStatus.RETRYING
    assert persisted.locked_by is None
    assert persisted.run_after is not None

