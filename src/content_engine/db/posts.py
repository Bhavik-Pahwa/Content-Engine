"""Post artifact persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from sqlite3 import Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import Platform, PostArtifact, PostArtifactStatus


@dataclass(frozen=True)
class PostArtifactStats:
    total: int
    draft: int
    approved: int
    average_post_length: float


class PostArtifactRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        content_item_id: str,
        platform: Platform,
        title: str,
        hook: str,
        body: str,
        call_to_action: str,
        hashtags: tuple[str, ...],
        estimated_reading_time_seconds: int,
        generation_metadata: dict[str, Any],
        provider_metadata: dict[str, Any],
        status: PostArtifactStatus = PostArtifactStatus.DRAFT,
    ) -> PostArtifact:
        now = _now()
        artifact_id = str(uuid.uuid4())
        version_number = self.next_version_number(content_item_id, platform)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO post_artifacts (
                    id, content_item_id, platform, version_number, title,
                    hook, body, call_to_action, hashtags_json,
                    estimated_reading_time_seconds, generation_metadata_json,
                    provider_metadata_json, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    content_item_id,
                    platform.value,
                    version_number,
                    title,
                    hook,
                    body,
                    call_to_action,
                    json.dumps(list(hashtags), sort_keys=True),
                    estimated_reading_time_seconds,
                    json.dumps(generation_metadata, sort_keys=True),
                    json.dumps(provider_metadata, sort_keys=True),
                    status.value,
                    _format_datetime(now),
                    _format_datetime(now),
                ),
            )
        return self.required(artifact_id)

    def get(self, artifact_id: str) -> PostArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM post_artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return _row_to_artifact(row) if row else None

    def required(self, artifact_id: str) -> PostArtifact:
        artifact = self.get(artifact_id)
        if artifact is None:
            raise LookupError(f"Post artifact not found: {artifact_id}")
        return artifact

    def latest_for_content_item(self, content_item_id: str, platform: Platform) -> PostArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM post_artifacts
                WHERE content_item_id = ? AND platform = ?
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (content_item_id, platform.value),
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def list_for_content_item(self, content_item_id: str, platform: Platform | None = None) -> list[PostArtifact]:
        with self.database.connect() as connection:
            if platform is None:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM post_artifacts
                    WHERE content_item_id = ?
                    ORDER BY platform ASC, version_number ASC
                    """,
                    (content_item_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM post_artifacts
                    WHERE content_item_id = ? AND platform = ?
                    ORDER BY version_number ASC
                    """,
                    (content_item_id, platform.value),
                ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def next_version_number(self, content_item_id: str, platform: Platform) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
                FROM post_artifacts
                WHERE content_item_id = ? AND platform = ?
                """,
                (content_item_id, platform.value),
            ).fetchone()
        return int(row["next_version"])

    def stats(self) -> PostArtifactStats:
        with self.database.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) AS count FROM post_artifacts").fetchone()["count"])
            draft = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM post_artifacts WHERE status = ?",
                    (PostArtifactStatus.DRAFT.value,),
                ).fetchone()["count"]
            )
            approved = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM post_artifacts WHERE status = ?",
                    (PostArtifactStatus.APPROVED.value,),
                ).fetchone()["count"]
            )
            rows = connection.execute("SELECT hook, body, call_to_action FROM post_artifacts").fetchall()
        lengths = [len(str(row["hook"])) + len(str(row["body"])) + len(str(row["call_to_action"])) for row in rows]
        return PostArtifactStats(
            total=total,
            draft=draft,
            approved=approved,
            average_post_length=sum(lengths) / len(lengths) if lengths else 0.0,
        )


def _row_to_artifact(row: Row) -> PostArtifact:
    return PostArtifact(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        platform=Platform(str(row["platform"])),
        version_number=int(row["version_number"]),
        title=str(row["title"]),
        hook=str(row["hook"]),
        body=str(row["body"]),
        call_to_action=str(row["call_to_action"]),
        hashtags=tuple(str(item) for item in json.loads(str(row["hashtags_json"] or "[]"))),
        estimated_reading_time_seconds=int(row["estimated_reading_time_seconds"]),
        generation_metadata=json.loads(str(row["generation_metadata_json"] or "{}")),
        provider_metadata=json.loads(str(row["provider_metadata_json"] or "{}")),
        status=PostArtifactStatus(str(row["status"])),
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
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
