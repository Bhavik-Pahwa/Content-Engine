"""Publication artifact persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import Platform, PublicationArtifact, PublishingStatus


@dataclass(frozen=True)
class PublicationStats:
    total: int
    published: int
    failed: int
    skipped: int


class PublicationArtifactRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_attempt(
        self,
        *,
        content_item_id: str,
        platform: Platform,
        post_artifact_id: str,
        image_artifact_id: str | None,
        playwright_session: str | None,
        metadata: dict[str, Any],
    ) -> PublicationArtifact:
        artifact_id = str(uuid.uuid4())
        retry_count = self.attempt_count(content_item_id, platform)
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO publication_artifacts (
                    id, content_item_id, platform, post_artifact_id,
                    image_artifact_id, status, playwright_session,
                    retry_count, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    content_item_id,
                    platform.value,
                    post_artifact_id,
                    image_artifact_id,
                    PublishingStatus.PUBLISHING.value,
                    playwright_session,
                    retry_count,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    _format_datetime(now),
                ),
            )
        return self.required(artifact_id)

    def mark_published(
        self,
        artifact_id: str,
        *,
        url: str | None,
        screenshot_before_path: Path | None,
        screenshot_after_path: Path | None,
        duration_seconds: float,
        metadata: dict[str, Any],
    ) -> PublicationArtifact:
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE publication_artifacts
                SET status = ?, publish_timestamp = ?, url = ?,
                    screenshot_before_path = ?, screenshot_after_path = ?,
                    duration_seconds = ?, metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    PublishingStatus.PUBLISHED.value,
                    _format_datetime(now),
                    url,
                    _path_str(screenshot_before_path),
                    _path_str(screenshot_after_path),
                    duration_seconds,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    artifact_id,
                ),
            )
        return self.required(artifact_id)

    def mark_failed(
        self,
        artifact_id: str,
        *,
        error: str,
        screenshot_before_path: Path | None,
        screenshot_error_path: Path | None,
        duration_seconds: float,
        metadata: dict[str, Any],
    ) -> PublicationArtifact:
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE publication_artifacts
                SET status = ?, error = ?, screenshot_before_path = ?,
                    screenshot_error_path = ?, duration_seconds = ?,
                    metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    PublishingStatus.FAILED.value,
                    error,
                    _path_str(screenshot_before_path),
                    _path_str(screenshot_error_path),
                    duration_seconds,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    artifact_id,
                ),
            )
        return self.required(artifact_id)

    def mark_skipped(
        self,
        artifact_id: str,
        *,
        error: str | None,
        screenshot_before_path: Path | None,
        screenshot_after_path: Path | None,
        duration_seconds: float,
        metadata: dict[str, Any],
    ) -> PublicationArtifact:
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE publication_artifacts
                SET status = ?, error = ?, screenshot_before_path = ?,
                    screenshot_after_path = ?, duration_seconds = ?,
                    metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    PublishingStatus.SKIPPED.value,
                    error,
                    _path_str(screenshot_before_path),
                    _path_str(screenshot_after_path),
                    duration_seconds,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    artifact_id,
                ),
            )
        return self.required(artifact_id)

    def get(self, artifact_id: str) -> PublicationArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM publication_artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return _row_to_artifact(row) if row else None

    def required(self, artifact_id: str) -> PublicationArtifact:
        artifact = self.get(artifact_id)
        if artifact is None:
            raise LookupError(f"Publication artifact not found: {artifact_id}")
        return artifact

    def latest_for_content_item(self, content_item_id: str, platform: Platform) -> PublicationArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM publication_artifacts
                WHERE content_item_id = ? AND platform = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (content_item_id, platform.value),
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def published_for_content_item(self, content_item_id: str, platform: Platform) -> PublicationArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM publication_artifacts
                WHERE content_item_id = ? AND platform = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (content_item_id, platform.value, PublishingStatus.PUBLISHED.value),
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def attempt_count(self, content_item_id: str, platform: Platform) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM publication_artifacts
                WHERE content_item_id = ? AND platform = ?
                """,
                (content_item_id, platform.value),
            ).fetchone()
        return int(row["count"])

    def stats(self) -> PublicationStats:
        with self.database.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) AS count FROM publication_artifacts").fetchone()["count"])
            published = _count_status(connection, PublishingStatus.PUBLISHED)
            failed = _count_status(connection, PublishingStatus.FAILED)
            skipped = _count_status(connection, PublishingStatus.SKIPPED)
        return PublicationStats(total=total, published=published, failed=failed, skipped=skipped)


def _row_to_artifact(row: Row) -> PublicationArtifact:
    return PublicationArtifact(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        platform=Platform(str(row["platform"])),
        post_artifact_id=str(row["post_artifact_id"]),
        image_artifact_id=None if row["image_artifact_id"] is None else str(row["image_artifact_id"]),
        status=PublishingStatus(str(row["status"])),
        publish_timestamp=_parse_datetime(row["publish_timestamp"]),
        playwright_session=None if row["playwright_session"] is None else str(row["playwright_session"]),
        url=None if row["url"] is None else str(row["url"]),
        retry_count=int(row["retry_count"]),
        error=None if row["error"] is None else str(row["error"]),
        screenshot_before_path=_path(row["screenshot_before_path"]),
        screenshot_after_path=_path(row["screenshot_after_path"]),
        screenshot_error_path=_path(row["screenshot_error_path"]),
        duration_seconds=float(row["duration_seconds"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=_parse_datetime(row["created_at"]) or _now(),
        updated_at=_parse_datetime(row["updated_at"]) or _now(),
    )


def _count_status(connection, status: PublishingStatus) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM publication_artifacts WHERE status = ?",
        (status.value,),
    ).fetchone()
    return int(row["count"])


def _path(value: Any) -> Path | None:
    return None if value is None else Path(str(value))


def _path_str(value: Path | None) -> str | None:
    return None if value is None else str(value)


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
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
