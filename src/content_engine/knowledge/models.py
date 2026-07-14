"""Internal models for knowledge acquisition."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    content_type: str
    html: str
    status_code: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedArticle:
    title: str
    clean_text: str
    author: str | None
    publication_date: datetime | None
    canonical_url: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeProcessingResult:
    summary: str
    keywords: tuple[str, ...]
    named_entities: tuple[str, ...]
    technology_tags: tuple[str, ...]
    companies: tuple[str, ...]
    people: tuple[str, ...]
    concepts: tuple[str, ...]
    word_count: int
    language: str
    reading_time_minutes: int
    reading_difficulty: str
    estimated_audience: str
    technology_category: str


@dataclass(frozen=True)
class KnowledgeBuildStats:
    articles_fetched: int = 0
    extraction_success: int = 0
    extraction_failures: int = 0
    average_processing_time_seconds: float = 0.0
    average_article_length_words: float = 0.0
    keyword_count: int = 0
    documents_created: int = 0
    failures: int = 0

    def as_metadata(self) -> dict[str, Any]:
        return {
            "articles_fetched": self.articles_fetched,
            "extraction_success": self.extraction_success,
            "extraction_failures": self.extraction_failures,
            "average_processing_time_seconds": self.average_processing_time_seconds,
            "average_article_length_words": self.average_article_length_words,
            "keyword_count": self.keyword_count,
            "documents_created": self.documents_created,
            "failures": self.failures,
        }

