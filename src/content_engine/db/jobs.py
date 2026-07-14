"""Persistent job queue repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from sqlite3 import Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import Job, JobStatus


@dataclass(frozen=True)
class QueueStats:
    pending: int = 0
    retrying: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0

    @property
    def executable(self) -> int:
        return self.pending + self.retrying


class JobRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        job_type: str,
        payload: dict[str, Any] | None = None,
        priority: int = 100,
        max_attempts: int = 3,
        run_after: datetime | None = None,
        dependencies: list[str] | None = None,
    ) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            job_type=job_type,
            priority=priority,
            payload=payload or {},
            dependencies=tuple(dependencies or ()),
            max_attempts=max_attempts,
            run_after=run_after,
        )
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, job_type, status, priority, payload_json, attempts,
                    max_attempts, run_after, dependencies_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.job_type,
                    job.status.value,
                    job.priority,
                    json.dumps(job.payload, sort_keys=True),
                    job.attempts,
                    job.max_attempts,
                    _format_datetime(job.run_after),
                    json.dumps(dependencies or [], sort_keys=True),
                    _format_datetime(now),
                    _format_datetime(now),
                ),
            )
        return self.get(job.id) or job

    def get(self, job_id: str) -> Job | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def claim_next(self, *, worker_id: str, now: datetime | None = None) -> Job | None:
        timestamp = now or _now()
        timestamp_text = _format_datetime(timestamp)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE status IN (?, ?)
                  AND (run_after IS NULL OR run_after <= ?)
                ORDER BY priority ASC, COALESCE(run_after, created_at) ASC, created_at ASC
                LIMIT 100
                """,
                (JobStatus.PENDING.value, JobStatus.RETRYING.value, timestamp_text),
            ).fetchall()
            row = next((candidate for candidate in rows if self._dependencies_completed(connection, candidate)), None)
            if row is None:
                return None
            attempts = int(row["attempts"]) + 1
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, attempts = ?, locked_by = ?, locked_at = ?,
                    started_at = COALESCE(started_at, ?), updated_at = ?, last_error = NULL
                WHERE id = ?
                """,
                (
                    JobStatus.RUNNING.value,
                    attempts,
                    worker_id,
                    timestamp_text,
                    timestamp_text,
                    timestamp_text,
                    row["id"],
                ),
            )
        return self.get(str(row["id"]))

    def find_existing(
        self,
        *,
        job_type: str,
        payload: dict[str, Any],
        statuses: tuple[JobStatus, ...] | None = None,
    ) -> Job | None:
        payload_json = json.dumps(payload, sort_keys=True)
        status_values = tuple(status.value for status in statuses) if statuses else None
        with self.database.connect() as connection:
            if status_values:
                placeholders = ",".join("?" for _ in status_values)
                row = connection.execute(
                    f"""
                    SELECT *
                    FROM jobs
                    WHERE job_type = ?
                      AND payload_json = ?
                      AND status IN ({placeholders})
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (job_type, payload_json, *status_values),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT *
                    FROM jobs
                    WHERE job_type = ? AND payload_json = ?
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (job_type, payload_json),
                ).fetchone()
        return _row_to_job(row) if row else None

    def mark_completed(self, job_id: str, *, now: datetime | None = None) -> Job:
        timestamp = now or _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, locked_by = NULL, locked_at = NULL,
                    completed_at = ?, updated_at = ?, last_error = NULL
                WHERE id = ?
                """,
                (JobStatus.COMPLETED.value, _format_datetime(timestamp), _format_datetime(timestamp), job_id),
            )
        return self._required(job_id)

    def mark_failed(self, job_id: str, *, error: str, now: datetime | None = None) -> Job:
        timestamp = now or _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, locked_by = NULL, locked_at = NULL,
                    completed_at = ?, updated_at = ?, last_error = ?
                WHERE id = ?
                """,
                (JobStatus.FAILED.value, _format_datetime(timestamp), _format_datetime(timestamp), error, job_id),
            )
        return self._required(job_id)

    def mark_retrying(
        self,
        job_id: str,
        *,
        error: str,
        run_after: datetime,
        now: datetime | None = None,
    ) -> Job:
        timestamp = now or _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, locked_by = NULL, locked_at = NULL,
                    run_after = ?, updated_at = ?, last_error = ?
                WHERE id = ?
                """,
                (JobStatus.RETRYING.value, _format_datetime(run_after), _format_datetime(timestamp), error, job_id),
            )
        return self._required(job_id)

    def cancel(self, job_id: str, *, reason: str | None = None, now: datetime | None = None) -> Job:
        timestamp = now or _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, locked_by = NULL, locked_at = NULL,
                    completed_at = ?, updated_at = ?, last_error = ?
                WHERE id = ?
                """,
                (JobStatus.CANCELLED.value, _format_datetime(timestamp), _format_datetime(timestamp), reason, job_id),
            )
        return self._required(job_id)

    def recover_stale_running(
        self,
        *,
        older_than: timedelta,
        retry_delay: timedelta,
        now: datetime | None = None,
    ) -> int:
        timestamp = now or _now()
        cutoff = timestamp - older_than
        recovered = 0
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, attempts, max_attempts
                FROM jobs
                WHERE status = ? AND locked_at IS NOT NULL AND locked_at < ?
                """,
                (JobStatus.RUNNING.value, _format_datetime(cutoff)),
            ).fetchall()
            for row in rows:
                if int(row["attempts"]) >= int(row["max_attempts"]):
                    status = JobStatus.FAILED.value
                    run_after = None
                    completed_at = _format_datetime(timestamp)
                else:
                    status = JobStatus.RETRYING.value
                    run_after = _format_datetime(timestamp + retry_delay)
                    completed_at = None
                connection.execute(
                    """
                    UPDATE jobs
                    SET status = ?, locked_by = NULL, locked_at = NULL,
                        run_after = ?, completed_at = ?, updated_at = ?,
                        last_error = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        run_after,
                        completed_at,
                        _format_datetime(timestamp),
                        "Recovered stale running job after restart",
                        row["id"],
                    ),
                )
                recovered += 1
        return recovered

    def stats(self) -> QueueStats:
        counts = {status.value: 0 for status in JobStatus}
        with self.database.connect() as connection:
            rows = connection.execute("SELECT status, COUNT(*) AS count FROM jobs GROUP BY status").fetchall()
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        return QueueStats(
            pending=counts[JobStatus.PENDING.value],
            retrying=counts[JobStatus.RETRYING.value],
            running=counts[JobStatus.RUNNING.value],
            completed=counts[JobStatus.COMPLETED.value],
            failed=counts[JobStatus.FAILED.value],
            cancelled=counts[JobStatus.CANCELLED.value],
        )

    def list_by_status(self, status: JobStatus) -> list[Job]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC",
                (status.value,),
            ).fetchall()
        return [_row_to_job(row) for row in rows]

    def _required(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job is None:
            raise LookupError(f"Job not found: {job_id}")
        return job

    @staticmethod
    def _dependencies_completed(connection, row: Row) -> bool:
        dependency_ids = json.loads(str(row["dependencies_json"] or "[]"))
        if not dependency_ids:
            return True
        placeholders = ",".join("?" for _ in dependency_ids)
        rows = connection.execute(
            f"SELECT id, status FROM jobs WHERE id IN ({placeholders})",
            tuple(dependency_ids),
        ).fetchall()
        if len(rows) != len(dependency_ids):
            return False
        return all(str(dependency["status"]) == JobStatus.COMPLETED.value for dependency in rows)


def _row_to_job(row: Row) -> Job:
    return Job(
        id=str(row["id"]),
        job_type=str(row["job_type"]),
        status=JobStatus(str(row["status"])),
        priority=int(row["priority"]),
        payload=json.loads(str(row["payload_json"] or "{}")),
        dependencies=tuple(json.loads(str(row["dependencies_json"] or "[]"))),
        attempts=int(row["attempts"]),
        max_attempts=int(row["max_attempts"]),
        run_after=_parse_datetime(row["run_after"]),
        locked_by=None if row["locked_by"] is None else str(row["locked_by"]),
        locked_at=_parse_datetime(row["locked_at"]),
        last_error=None if row["last_error"] is None else str(row["last_error"]),
        created_at=_parse_datetime(row["created_at"]) or _now(),
        updated_at=_parse_datetime(row["updated_at"]) or _now(),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
