"""Knowledge document persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import KnowledgeDocument, KnowledgeDocumentStatus


class KnowledgeRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        topic_id: str,
        title: str,
        summary: str,
        clean_text: str,
        keywords: tuple[str, ...],
        named_entities: tuple[str, ...],
        technology_tags: tuple[str, ...],
        companies: tuple[str, ...],
        people: tuple[str, ...],
        concepts: tuple[str, ...],
        source_url: str,
        canonical_url: str | None,
        author: str | None,
        publication_date: datetime | None,
        word_count: int,
        language: str,
        reading_time_minutes: int,
        reading_difficulty: str,
        estimated_audience: str,
        technology_category: str,
        raw_html: str | None,
        metadata: dict[str, Any],
        status: KnowledgeDocumentStatus = KnowledgeDocumentStatus.CREATED,
    ) -> KnowledgeDocument:
        now = _now()
        document_id = str(uuid.uuid4())
        version_number = self.next_version_number(topic_id)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_documents (
                    id, topic_id, version_number, title, summary, clean_text,
                    keywords_json, named_entities_json, technology_tags_json,
                    companies_json, people_json, concepts_json, source_url,
                    canonical_url, author, publication_date, word_count,
                    language, reading_time_minutes, reading_difficulty,
                    estimated_audience, technology_category, status, raw_html,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    topic_id,
                    version_number,
                    title,
                    summary,
                    clean_text,
                    _json_tuple(keywords),
                    _json_tuple(named_entities),
                    _json_tuple(technology_tags),
                    _json_tuple(companies),
                    _json_tuple(people),
                    _json_tuple(concepts),
                    source_url,
                    canonical_url,
                    author,
                    _format_datetime(publication_date),
                    word_count,
                    language,
                    reading_time_minutes,
                    reading_difficulty,
                    estimated_audience,
                    technology_category,
                    status.value,
                    raw_html,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    _format_datetime(now),
                ),
            )
        return self.required(document_id)

    def get(self, document_id: str) -> KnowledgeDocument | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM knowledge_documents WHERE id = ?", (document_id,)).fetchone()
        return _row_to_document(row) if row else None

    def required(self, document_id: str) -> KnowledgeDocument:
        document = self.get(document_id)
        if document is None:
            raise LookupError(f"Knowledge document not found: {document_id}")
        return document

    def list_for_topic(self, topic_id: str) -> list[KnowledgeDocument]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_documents WHERE topic_id = ? ORDER BY version_number ASC",
                (topic_id,),
            ).fetchall()
        return [_row_to_document(row) for row in rows]

    def count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM knowledge_documents").fetchone()
        return int(row["count"])

    def next_version_number(self, topic_id: str) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM knowledge_documents WHERE topic_id = ?",
                (topic_id,),
            ).fetchone()
        return int(row["next_version"])


def _row_to_document(row: Row) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=str(row["id"]),
        topic_id=str(row["topic_id"]),
        version_number=int(row["version_number"]),
        title=str(row["title"]),
        summary=str(row["summary"]),
        clean_text=str(row["clean_text"]),
        keywords=_tuple(row["keywords_json"]),
        named_entities=_tuple(row["named_entities_json"]),
        technology_tags=_tuple(row["technology_tags_json"]),
        companies=_tuple(row["companies_json"]),
        people=_tuple(row["people_json"]),
        concepts=_tuple(row["concepts_json"]),
        source_url=str(row["source_url"]),
        canonical_url=None if row["canonical_url"] is None else str(row["canonical_url"]),
        author=None if row["author"] is None else str(row["author"]),
        publication_date=_parse_datetime(row["publication_date"]),
        word_count=int(row["word_count"]),
        language=str(row["language"]),
        reading_time_minutes=int(row["reading_time_minutes"]),
        reading_difficulty=str(row["reading_difficulty"]),
        estimated_audience=str(row["estimated_audience"]),
        technology_category=str(row["technology_category"]),
        status=KnowledgeDocumentStatus(str(row["status"])),
        raw_html=None if row["raw_html"] is None else str(row["raw_html"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=_parse_datetime(row["created_at"]) or _now(),
        updated_at=_parse_datetime(row["updated_at"]) or _now(),
    )


def _json_tuple(values: tuple[str, ...]) -> str:
    return json.dumps(list(values), sort_keys=True)


def _tuple(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in json.loads(str(value or "[]")))


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
