"""Content item lifecycle persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from sqlite3 import IntegrityError, Row
from typing import Any
import json
import uuid

from content_engine.content_lifecycle.fsm import ContentLifecycleStateMachine
from content_engine.db.connection import Database
from content_engine.domain import (
    ArtifactType,
    ContentArtifact,
    ContentItem,
    ContentItemStage,
    ContentItemStatus,
    ContentStageTransition,
)


@dataclass(frozen=True)
class ContentLifecycleStats:
    items_created: int
    stage_distribution: dict[str, int]
    failed_items: int
    archived_items: int
    average_completion_seconds: float


class ContentItemRepository:
    def __init__(self, database: Database, fsm: ContentLifecycleStateMachine | None = None) -> None:
        self.database = database
        self.fsm = fsm or ContentLifecycleStateMachine()

    def create(
        self,
        *,
        title: str,
        source_topic_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContentItem:
        existing = self.find_by_topic(source_topic_id) if source_topic_id else None
        if existing is not None:
            return existing
        item_id = str(uuid.uuid4())
        now = _now()
        try:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO content_items (
                        id, title, stage, status, source_topic_id,
                        metadata_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        title,
                        ContentItemStage.DISCOVERED.value,
                        ContentItemStatus.ACTIVE.value,
                        source_topic_id,
                        json.dumps(metadata or {}, sort_keys=True),
                        _format_datetime(now),
                        _format_datetime(now),
                    ),
                )
                self._insert_transition(
                    connection,
                    content_item_id=item_id,
                    from_stage=None,
                    to_stage=ContentItemStage.DISCOVERED,
                    reason="content item created",
                    job_id=None,
                    now=now,
                )
        except IntegrityError:
            if source_topic_id:
                existing = self.find_by_topic(source_topic_id)
                if existing is not None:
                    return existing
            raise
        return self.required(item_id)

    def get(self, content_item_id: str) -> ContentItem | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM content_items WHERE id = ?", (content_item_id,)).fetchone()
        return _row_to_item(row) if row else None

    def required(self, content_item_id: str) -> ContentItem:
        item = self.get(content_item_id)
        if item is None:
            raise LookupError(f"Content item not found: {content_item_id}")
        return item

    def find_by_topic(self, topic_id: str | None) -> ContentItem | None:
        if topic_id is None:
            return None
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM content_items WHERE source_topic_id = ?", (topic_id,)).fetchone()
        return _row_to_item(row) if row else None

    def transition(
        self,
        content_item_id: str,
        to_stage: ContentItemStage,
        *,
        reason: str | None = None,
        job_id: str | None = None,
    ) -> ContentItem:
        item = self.required(content_item_id)
        self.fsm.require_transition(item.stage, to_stage)
        now = _now()
        status = item.status
        if status == ContentItemStatus.FAILED:
            status = ContentItemStatus.ACTIVE
        if to_stage == ContentItemStage.PUBLISHED:
            status = ContentItemStatus.COMPLETED
        if to_stage == ContentItemStage.ARCHIVED:
            status = ContentItemStatus.ARCHIVED
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE content_items
                SET stage = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (to_stage.value, status.value, _format_datetime(now), content_item_id),
            )
            self._insert_transition(
                connection,
                content_item_id=content_item_id,
                from_stage=item.stage,
                to_stage=to_stage,
                reason=reason,
                job_id=job_id,
                now=now,
            )
        return self.required(content_item_id)

    def mark_failed(self, content_item_id: str, *, reason: str, job_id: str | None = None) -> ContentItem:
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE content_items
                SET status = ?, failure_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (ContentItemStatus.FAILED.value, reason, _format_datetime(now), content_item_id),
            )
        return self.required(content_item_id)

    def attach_artifact(
        self,
        *,
        content_item_id: str,
        artifact_type: ArtifactType,
        artifact_id: str,
        role: str = "primary",
        metadata: dict[str, Any] | None = None,
    ) -> ContentArtifact:
        existing = self.find_artifact(
            content_item_id=content_item_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            role=role,
        )
        if existing is not None:
            return existing
        artifact_link_id = str(uuid.uuid4())
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO content_item_artifacts (
                    id, content_item_id, artifact_type, artifact_id,
                    role, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_link_id,
                    content_item_id,
                    artifact_type.value,
                    artifact_id,
                    role,
                    json.dumps(metadata or {}, sort_keys=True),
                    _format_datetime(now),
                ),
            )
        return self.required_artifact(artifact_link_id)

    def find_artifact(
        self,
        *,
        content_item_id: str,
        artifact_type: ArtifactType,
        artifact_id: str,
        role: str,
    ) -> ContentArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM content_item_artifacts
                WHERE content_item_id = ? AND artifact_type = ? AND artifact_id = ? AND role = ?
                """,
                (content_item_id, artifact_type.value, artifact_id, role),
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def required_artifact(self, artifact_link_id: str) -> ContentArtifact:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM content_item_artifacts WHERE id = ?", (artifact_link_id,)).fetchone()
        if row is None:
            raise LookupError(f"Content artifact link not found: {artifact_link_id}")
        return _row_to_artifact(row)

    def artifacts_for_item(self, content_item_id: str) -> list[ContentArtifact]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM content_item_artifacts WHERE content_item_id = ? ORDER BY created_at ASC",
                (content_item_id,),
            ).fetchall()
        return [_row_to_artifact(row) for row in rows]

    def stage_history(self, content_item_id: str) -> list[ContentStageTransition]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM content_item_stage_history WHERE content_item_id = ? ORDER BY created_at ASC",
                (content_item_id,),
            ).fetchall()
        return [_row_to_transition(row) for row in rows]

    def stats(self) -> ContentLifecycleStats:
        with self.database.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) AS count FROM content_items").fetchone()["count"])
            rows = connection.execute("SELECT stage, COUNT(*) AS count FROM content_items GROUP BY stage").fetchall()
            failed = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM content_items WHERE status = ?",
                    (ContentItemStatus.FAILED.value,),
                ).fetchone()["count"]
            )
            archived = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM content_items WHERE status = ?",
                    (ContentItemStatus.ARCHIVED.value,),
                ).fetchone()["count"]
            )
            completed_rows = connection.execute(
                """
                SELECT created_at, updated_at
                FROM content_items
                WHERE status IN (?, ?)
                """,
                (ContentItemStatus.COMPLETED.value, ContentItemStatus.ARCHIVED.value),
            ).fetchall()
        durations = [
            (_parse_datetime(row["updated_at"]) - _parse_datetime(row["created_at"])).total_seconds()
            for row in completed_rows
            if _parse_datetime(row["updated_at"]) and _parse_datetime(row["created_at"])
        ]
        return ContentLifecycleStats(
            items_created=total,
            stage_distribution={str(row["stage"]): int(row["count"]) for row in rows},
            failed_items=failed,
            archived_items=archived,
            average_completion_seconds=sum(durations) / len(durations) if durations else 0.0,
        )

    @staticmethod
    def _insert_transition(
        connection,
        *,
        content_item_id: str,
        from_stage: ContentItemStage | None,
        to_stage: ContentItemStage,
        reason: str | None,
        job_id: str | None,
        now: datetime,
    ) -> None:
        connection.execute(
            """
            INSERT INTO content_item_stage_history (
                id, content_item_id, from_stage, to_stage, reason, job_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                content_item_id,
                from_stage.value if from_stage else None,
                to_stage.value,
                reason,
                job_id,
                _format_datetime(now),
            ),
        )


def _row_to_item(row: Row) -> ContentItem:
    return ContentItem(
        id=str(row["id"]),
        title=str(row["title"]),
        stage=ContentItemStage(str(row["stage"])),
        status=ContentItemStatus(str(row["status"])),
        source_topic_id=None if row["source_topic_id"] is None else str(row["source_topic_id"]),
        failure_reason=None if row["failure_reason"] is None else str(row["failure_reason"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=_parse_datetime(row["created_at"]) or _now(),
        updated_at=_parse_datetime(row["updated_at"]) or _now(),
    )


def _row_to_artifact(row: Row) -> ContentArtifact:
    return ContentArtifact(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        artifact_type=ArtifactType(str(row["artifact_type"])),
        artifact_id=str(row["artifact_id"]),
        role=str(row["role"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=_parse_datetime(row["created_at"]) or _now(),
    )


def _row_to_transition(row: Row) -> ContentStageTransition:
    return ContentStageTransition(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        from_stage=None if row["from_stage"] is None else ContentItemStage(str(row["from_stage"])),
        to_stage=ContentItemStage(str(row["to_stage"])),
        reason=None if row["reason"] is None else str(row["reason"]),
        job_id=None if row["job_id"] is None else str(row["job_id"]),
        created_at=_parse_datetime(row["created_at"]) or _now(),
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
