from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.discovery.deduplication import TopicDeduplicator
from content_engine.discovery.filters import TopicFilter
from content_engine.discovery.jobs import DISCOVER_TOPICS, DiscoverTopicsJobHandler
from content_engine.discovery.models import TopicCandidate
from content_engine.discovery.providers import HackerNewsProvider
from content_engine.discovery.service import TopicDiscoveryError, TopicDiscoveryService
from content_engine.domain import JobStatus
from content_engine.observability import get_logger
from content_engine.orchestration import JobExecutionEngine, JobHandlerRegistry, JobResult, RetryPolicy, RuntimeMetrics
from datetime import timedelta


class FakeHackerNewsClient:
    def __init__(self, items: dict[int, dict[str, Any] | None], ids: list[int] | None = None) -> None:
        self.items = items
        self.ids = ids if ids is not None else list(items)

    def top_story_ids(self, *, timeout_seconds: float) -> list[int]:
        return self.ids

    def item(self, item_id: int, *, timeout_seconds: float) -> dict[str, Any] | None:
        return self.items.get(item_id)


class FailingProvider:
    def discover_topics(self) -> list[TopicCandidate]:
        raise RuntimeError("network down")


class StaticProvider:
    def __init__(self, candidates: list[TopicCandidate]) -> None:
        self.candidates = candidates

    def discover_topics(self) -> list[TopicCandidate]:
        return self.candidates


def repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def test_hacker_news_provider_parses_valid_stories_and_ignores_invalid_items() -> None:
    provider = HackerNewsProvider(
        fetch_limit=4,
        request_timeout_seconds=1,
        retry_count=0,
        client=FakeHackerNewsClient(
            {
                1: {
                    "id": 1,
                    "type": "story",
                    "title": "Open source database internals",
                    "url": "https://example.com/db",
                    "by": "alice",
                    "score": 42,
                    "time": 1_700_000_000,
                },
                2: {"id": 2, "type": "comment", "title": "nope"},
                3: {"id": 3, "type": "story", "deleted": True, "title": "deleted"},
                4: None,
            }
        ),
    )

    candidates = provider.discover_topics()

    assert len(candidates) == 1
    assert candidates[0].title == "Open source database internals"
    assert candidates[0].provider_name == "hacker_news"
    assert candidates[0].score == 42


def test_topic_filter_accepts_configured_categories() -> None:
    topic_filter = TopicFilter({"programming": ("python",)})

    accepted = topic_filter.evaluate(candidate("Python packaging improves"))
    rejected = topic_filter.evaluate(candidate("A history of ceramics"))

    assert accepted.accepted is True
    assert accepted.category == "programming"
    assert rejected.accepted is False


def test_topic_filter_does_not_match_short_keyword_inside_larger_word() -> None:
    topic_filter = TopicFilter({"artificial_intelligence": ("ai",)})

    rejected = topic_filter.evaluate(candidate("Interrail across Europe"))
    accepted = topic_filter.evaluate(candidate("AI-generated developer tooling"))

    assert rejected.accepted is False
    assert accepted.accepted is True


def test_duplicate_detection_uses_url_title_and_near_title(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    deduplicator = TopicDeduplicator(repos.topics, title_similarity_threshold=0.85)
    existing = candidate("Open source database internals", url="https://example.com/db?utm_source=hn")
    decision = deduplicator.evaluate(existing, set(), set())
    repos.topics.create(
        title=existing.title,
        source=existing.source,
        summary=existing.description,
        url=existing.url,
        author=existing.author,
        score=existing.score,
        provider_name=existing.provider_name,
        metadata={},
        published_at=existing.published_at,
        normalized_url=decision.normalized_url,
        normalized_title=decision.normalized_title,
    )

    duplicate_url = deduplicator.evaluate(candidate("Different title", url="https://example.com/db"), set(), set())
    duplicate_title = deduplicator.evaluate(candidate("Open source database internals", url="https://other.test"), set(), set())
    near_duplicate = deduplicator.evaluate(candidate("Open-source database internal", url="https://new.test"), set(), set())

    assert duplicate_url.duplicate is True
    assert duplicate_title.duplicate is True
    assert near_duplicate.duplicate is True


def test_discovery_service_filters_deduplicates_and_persists_topics(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    service = TopicDiscoveryService(
        providers=[
            StaticProvider(
                [
                    candidate("Python web framework released", url="https://example.com/python"),
                    candidate("Python web framework released", url="https://mirror.example.com/python"),
                    candidate("Best soup recipes", url="https://example.com/soup"),
                ]
            )
        ],
        topic_filter=TopicFilter({"programming": ("python",)}),
        deduplicator=TopicDeduplicator(repos.topics, title_similarity_threshold=0.9),
        topics=repos.topics,
        logger=get_logger("test"),
    )

    result = service.discover()

    assert len(result.topics) == 1
    assert result.stats.stories_fetched == 3
    assert result.stats.stories_accepted == 1
    assert result.stats.stories_rejected == 2
    assert result.stats.duplicate_count == 1
    assert repos.topics.count() == 1


def test_discovery_service_raises_when_all_providers_fail(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    service = TopicDiscoveryService(
        providers=[FailingProvider()],
        topic_filter=TopicFilter({"programming": ("python",)}),
        deduplicator=TopicDeduplicator(repos.topics, title_similarity_threshold=0.9),
        topics=repos.topics,
        logger=get_logger("test"),
    )

    with pytest.raises(TopicDiscoveryError):
        service.discover()


def test_discover_topics_job_executes_through_job_engine(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    service = TopicDiscoveryService(
        providers=[StaticProvider([candidate("Cloud security tooling", url="https://example.com/security")])],
        topic_filter=TopicFilter({"cloud": ("cloud",), "cybersecurity": ("security",)}),
        deduplicator=TopicDeduplicator(repos.topics, title_similarity_threshold=0.9),
        topics=repos.topics,
        logger=get_logger("test"),
    )
    handlers = JobHandlerRegistry()
    handlers.register(DISCOVER_TOPICS, DiscoverTopicsJobHandler(service))
    engine = JobExecutionEngine(
        jobs=repos.jobs,
        handlers=handlers,
        retry_policy=RetryPolicy(base_delay=timedelta(seconds=1), backoff_multiplier=2, max_delay=timedelta(seconds=10)),
        metrics=RuntimeMetrics(),
        logger=get_logger("test"),
    )
    job = repos.jobs.create(job_type=DISCOVER_TOPICS)
    claimed = repos.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)

    assert result.status == JobStatus.COMPLETED
    assert repos.topics.count() == 1


def candidate(title: str, url: str = "https://example.com/story") -> TopicCandidate:
    return TopicCandidate(
        title=title,
        url=url,
        source="test",
        provider_name="test_provider",
        description=None,
        author="author",
        score=10,
        published_at=datetime.now(timezone.utc),
        metadata={},
    )
