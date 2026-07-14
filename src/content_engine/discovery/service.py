"""Topic discovery service."""

from __future__ import annotations

from typing import Protocol
import logging
import time

from content_engine.db import TopicRepository
from content_engine.discovery.deduplication import TopicDeduplicator
from content_engine.discovery.filters import TopicFilter
from content_engine.discovery.models import DiscoveryResult, DiscoveryStats, TopicCandidate
from content_engine.domain import Topic


class TopicDiscoveryProvider(Protocol):
    def discover_topics(self) -> list[TopicCandidate]:
        """Return topic candidates from the provider."""


class TopicDiscoveryService:
    def __init__(
        self,
        *,
        providers: list[TopicDiscoveryProvider],
        topic_filter: TopicFilter,
        deduplicator: TopicDeduplicator,
        topics: TopicRepository,
        logger: logging.Logger,
    ) -> None:
        self.providers = providers
        self.topic_filter = topic_filter
        self.deduplicator = deduplicator
        self.topics = topics
        self.logger = logger

    def discover(self) -> DiscoveryResult:
        self.logger.info("topic_discovery_started", extra={"component": "discovery", "providers": len(self.providers)})
        inserted_topics: list[Topic] = []
        provider_response_times: dict[str, float] = {}
        providers_called = 0
        stories_fetched = 0
        stories_accepted = 0
        stories_rejected = 0
        duplicate_count = 0
        database_insertions = 0
        failures = 0
        seen_titles: set[str] = set()
        seen_urls: set[str] = set()

        for provider in self.providers:
            providers_called += 1
            provider_name = provider.__class__.__name__
            started = time.monotonic()
            try:
                self.logger.info(
                    "topic_provider_called",
                    extra={"component": "discovery", "provider": provider_name},
                )
                candidates = provider.discover_topics()
                elapsed = time.monotonic() - started
                provider_response_times[provider_name] = elapsed
                stories_fetched += len(candidates)
                self.logger.info(
                    "topic_provider_completed",
                    extra={
                        "component": "discovery",
                        "provider": provider_name,
                        "candidates": len(candidates),
                        "duration_seconds": elapsed,
                    },
                )
            except Exception:
                failures += 1
                elapsed = time.monotonic() - started
                provider_response_times[provider_name] = elapsed
                self.logger.exception(
                    "topic_provider_failed",
                    extra={"component": "discovery", "provider": provider_name, "duration_seconds": elapsed},
                )
                continue

            for candidate in candidates:
                filter_decision = self.topic_filter.evaluate(candidate)
                if not filter_decision.accepted:
                    stories_rejected += 1
                    continue
                duplicate_decision = self.deduplicator.evaluate(candidate, seen_titles, seen_urls)
                if duplicate_decision.duplicate:
                    duplicate_count += 1
                    stories_rejected += 1
                    continue
                metadata = {
                    **candidate.metadata,
                    "filter_category": filter_decision.category,
                    "filter_keyword": filter_decision.keyword,
                }
                topic = self.topics.create(
                    title=candidate.title,
                    source=candidate.source,
                    summary=candidate.description,
                    url=candidate.url,
                    author=candidate.author,
                    score=candidate.score,
                    provider_name=candidate.provider_name,
                    metadata=metadata,
                    published_at=candidate.published_at,
                    normalized_url=duplicate_decision.normalized_url,
                    normalized_title=duplicate_decision.normalized_title,
                )
                if topic is None:
                    duplicate_count += 1
                    stories_rejected += 1
                    continue
                stories_accepted += 1
                database_insertions += 1
                inserted_topics.append(topic)
                seen_titles.add(duplicate_decision.normalized_title)
                if duplicate_decision.normalized_url:
                    seen_urls.add(duplicate_decision.normalized_url)

        stats = DiscoveryStats(
            providers_called=providers_called,
            stories_fetched=stories_fetched,
            stories_accepted=stories_accepted,
            stories_rejected=stories_rejected,
            duplicate_count=duplicate_count,
            database_insertions=database_insertions,
            failures=failures,
            provider_response_time_seconds=provider_response_times,
        )
        if failures and failures == providers_called:
            self.logger.error("topic_discovery_failed", extra={"component": "discovery", **stats.as_metadata()})
            raise TopicDiscoveryError("All topic providers failed")
        self.logger.info("topic_discovery_completed", extra={"component": "discovery", **stats.as_metadata()})
        return DiscoveryResult(topics=tuple(inserted_topics), stats=stats)


class TopicDiscoveryError(RuntimeError):
    """Raised when topic discovery cannot produce a valid result."""
