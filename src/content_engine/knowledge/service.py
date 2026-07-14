"""Knowledge Engine service."""

from __future__ import annotations

import logging
import time

from content_engine.config import KnowledgeSettings
from content_engine.db import KnowledgeRepository, TopicRepository
from content_engine.domain import KnowledgeDocument
from content_engine.knowledge.extractor import ArticleExtractor
from content_engine.knowledge.fetcher import ContentFetcher
from content_engine.knowledge.models import KnowledgeBuildStats
from content_engine.knowledge.processor import KnowledgeProcessor


class KnowledgeService:
    def __init__(
        self,
        *,
        topics: TopicRepository,
        knowledge: KnowledgeRepository,
        fetcher: ContentFetcher,
        extractor: ArticleExtractor,
        processor: KnowledgeProcessor,
        settings: KnowledgeSettings,
        logger: logging.Logger,
    ) -> None:
        self.topics = topics
        self.knowledge = knowledge
        self.fetcher = fetcher
        self.extractor = extractor
        self.processor = processor
        self.settings = settings
        self.logger = logger

    def build_for_topic(self, topic_id: str) -> KnowledgeDocument:
        started = time.monotonic()
        topic = self.topics.get(topic_id)
        if topic is None:
            self.logger.error("knowledge_failed", extra={"component": "knowledge", "topic_id": topic_id, "error": "topic not found"})
            raise KnowledgeServiceError(f"Topic not found: {topic_id}")
        source_url = topic.source_url
        if not source_url:
            raise KnowledgeServiceError(f"Topic has no source URL: {topic_id}")
        self.logger.info("knowledge_fetch_started", extra={"component": "knowledge", "topic_id": topic_id, "source_url": source_url})
        fetch = self.fetcher.fetch(source_url)
        self.logger.info(
            "knowledge_fetch_completed",
            extra={"component": "knowledge", "topic_id": topic_id, "final_url": fetch.final_url, "content_type": fetch.content_type},
        )
        self.logger.info("knowledge_extraction_started", extra={"component": "knowledge", "topic_id": topic_id})
        try:
            article = self.extractor.extract(fetch)
        except Exception:
            self.logger.exception("knowledge_extraction_failed", extra={"component": "knowledge", "topic_id": topic_id})
            raise
        self.logger.info(
            "knowledge_extraction_completed",
            extra={"component": "knowledge", "topic_id": topic_id, "title": article.title, "word_count": len(article.clean_text.split())},
        )
        self.logger.info("knowledge_processing_started", extra={"component": "knowledge", "topic_id": topic_id})
        processed = self.processor.process(article)
        raw_html = fetch.html if self.settings.store_raw_html else None
        document = self.knowledge.create(
            topic_id=topic.id,
            title=article.title,
            summary=processed.summary,
            clean_text=article.clean_text,
            keywords=processed.keywords,
            named_entities=processed.named_entities,
            technology_tags=processed.technology_tags,
            companies=processed.companies,
            people=processed.people,
            concepts=processed.concepts,
            source_url=source_url,
            canonical_url=article.canonical_url,
            author=article.author,
            publication_date=article.publication_date,
            word_count=processed.word_count,
            language=processed.language,
            reading_time_minutes=processed.reading_time_minutes,
            reading_difficulty=processed.reading_difficulty,
            estimated_audience=processed.estimated_audience,
            technology_category=processed.technology_category,
            raw_html=raw_html,
            metadata={
                **fetch.metadata,
                **article.metadata,
                "final_url": fetch.final_url,
                "processing_strategy": "deterministic_local",
                "processing_time_seconds": time.monotonic() - started,
            },
        )
        stats = KnowledgeBuildStats(
            articles_fetched=1,
            extraction_success=1,
            average_processing_time_seconds=time.monotonic() - started,
            average_article_length_words=processed.word_count,
            keyword_count=len(processed.keywords),
            documents_created=1,
        )
        self.logger.info(
            "knowledge_stored",
            extra={"component": "knowledge", "topic_id": topic.id, "knowledge_document_id": document.id, **stats.as_metadata()},
        )
        self.logger.info("knowledge_completed", extra={"component": "knowledge", "topic_id": topic.id, "knowledge_document_id": document.id})
        return document


class KnowledgeServiceError(RuntimeError):
    """Raised when knowledge building cannot complete."""

