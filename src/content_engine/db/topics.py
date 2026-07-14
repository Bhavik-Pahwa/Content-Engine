"""Topic persistence and duplicate lookup."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import IntegrityError, Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import Topic, TopicStatus


class TopicRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        title: str,
        source: str,
        summary: str | None,
        url: str | None,
        author: str | None,
        score: int | None,
        provider_name: str,
        metadata: dict[str, Any],
        published_at: datetime | None,
        normalized_url: str | None,
        normalized_title: str,
    ) -> Topic | None:
        topic_id = str(uuid.uuid4())
        now = _now()
        try:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO topics (
                        id, title, summary, source, source_url, url, author, score,
                        status, provider_name, metadata_json, published_at,
                        discovered_at, created_at, updated_at, normalized_url, normalized_title
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic_id,
                        title,
                        summary,
                        source,
                        url,
                        url,
                        author,
                        score,
                        TopicStatus.DISCOVERED.value,
                        provider_name,
                        json.dumps(metadata, sort_keys=True),
                        _format_datetime(published_at),
                        _format_datetime(now),
                        _format_datetime(now),
                        _format_datetime(now),
                        normalized_url,
                        normalized_title,
                    ),
                )
        except IntegrityError:
            return None
        return self.get(topic_id)

    def get(self, topic_id: str) -> Topic | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        return _row_to_topic(row) if row else None

    def set_status(self, topic_id: str, status: TopicStatus) -> Topic:
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE topics
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, _format_datetime(now), topic_id),
            )
        topic = self.get(topic_id)
        if topic is None:
            raise LookupError(f"Topic not found: {topic_id}")
        return topic

    def exists_by_normalized_url(self, normalized_url: str | None) -> bool:
        if not normalized_url:
            return False
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM topics WHERE normalized_url = ? LIMIT 1",
                (normalized_url,),
            ).fetchone()
        return row is not None

    def exists_by_normalized_title(self, normalized_title: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM topics WHERE normalized_title = ? LIMIT 1",
                (normalized_title,),
            ).fetchone()
        return row is not None

    def normalized_titles(self) -> list[str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT normalized_title FROM topics WHERE normalized_title IS NOT NULL AND normalized_title != ''"
            ).fetchall()
        return [str(row["normalized_title"]) for row in rows]

    def count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM topics").fetchone()
        return int(row["count"])

    def list_all(self) -> list[Topic]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM topics ORDER BY discovered_at ASC").fetchall()
        return [_row_to_topic(row) for row in rows]


def _row_to_topic(row: Row) -> Topic:
    return Topic(
        id=str(row["id"]),
        title=str(row["title"]),
        source=str(row["source"]),
        summary=None if row["summary"] is None else str(row["summary"]),
        source_url=_first_text(row, "url", "source_url"),
        author=None if row["author"] is None else str(row["author"]),
        score=None if row["score"] is None else int(row["score"]),
        provider_name=None if row["provider_name"] is None else str(row["provider_name"]),
        status=TopicStatus(str(row["status"])),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        published_at=_parse_datetime(row["published_at"]),
        discovered_at=_parse_datetime(row["discovered_at"]),
        created_at=_parse_datetime(row["created_at"]) or _now(),
        updated_at=_parse_datetime(row["updated_at"]) or _now(),
    )


def _first_text(row: Row, *keys: str) -> str | None:
    for key in keys:
        try:
            value = row[key]
        except (IndexError, KeyError):
            continue
        if value is not None:
            return str(value)
    return None


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
