from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from content_engine.config import KnowledgeSettings
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.discovery.normalization import normalize_title, normalize_url
from content_engine.domain import JobStatus
from content_engine.knowledge.extractor import ArticleExtractionError, ArticleExtractor
from content_engine.knowledge.fetcher import KnowledgeFetchError
from content_engine.knowledge.jobs import BUILD_KNOWLEDGE, BuildKnowledgeJobHandler
from content_engine.knowledge.models import FetchResult
from content_engine.knowledge.processor import KnowledgeProcessor
from content_engine.knowledge.service import KnowledgeService
from content_engine.observability import get_logger
from content_engine.orchestration import JobExecutionEngine, JobHandlerRegistry, RetryPolicy, RuntimeMetrics


ARTICLE_HTML = """
<!doctype html>
<html>
  <head>
    <title>Ignored Browser Title</title>
    <link rel="canonical" href="https://example.com/canonical">
    <meta property="og:title" content="Kubernetes Security Lessons">
    <meta name="author" content="Alex Morgan">
    <meta property="article:published_time" content="2026-07-01T10:00:00Z">
  </head>
  <body>
    <nav>Subscribe Login Pricing</nav>
    <script>console.log("noise")</script>
    <article>
      <h1>Kubernetes Security Lessons</h1>
      <p>Kubernetes security work often fails when teams treat clusters as simple deployment targets instead of shared infrastructure products.</p>
      <p>Platform engineers need observability, encryption, policy automation, and incident response practices that match how software actually ships.</p>
      <p>OpenAI, Google, and GitHub teams have all influenced how developers think about cloud security, developer tools, and operational maturity.</p>
      <p>The practical lesson is to design guardrails early, review supply chain risk, and make secure defaults easier than custom exceptions.</p>
    </article>
    <footer>Cookie settings and unrelated links</footer>
  </body>
</html>
"""


class FakeFetcher:
    def __init__(self, html: str = ARTICLE_HTML, *, fail: bool = False, content_type: str = "text/html") -> None:
        self.html = html
        self.fail = fail
        self.content_type = content_type

    def fetch(self, url: str) -> FetchResult:
        if self.fail:
            raise KnowledgeFetchError("boom")
        return FetchResult(url=url, final_url="https://example.com/canonical", content_type=self.content_type, html=self.html)


def repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def create_topic(repos: RepositoryRegistry, url: str | None = "https://example.com/article") -> str:
    topic = repos.topics.create(
        title="Kubernetes security lessons",
        source="test",
        summary="A practical article about cloud infrastructure security.",
        url=url,
        author="alice",
        score=100,
        provider_name="test_provider",
        metadata={},
        published_at=datetime.now(timezone.utc),
        normalized_url=normalize_url(url),
        normalized_title=normalize_title("Kubernetes security lessons"),
    )
    assert topic is not None
    return topic.id


def service(repos: RepositoryRegistry, fetcher: FakeFetcher | None = None) -> KnowledgeService:
    settings = KnowledgeSettings(min_clean_text_words=20, store_raw_html=True)
    return KnowledgeService(
        topics=repos.topics,
        knowledge=repos.knowledge,
        fetcher=fetcher or FakeFetcher(),
        extractor=ArticleExtractor(min_clean_text_words=settings.min_clean_text_words),
        processor=KnowledgeProcessor(),
        settings=settings,
        logger=get_logger("test"),
    )


def test_article_extraction_removes_navigation_and_reads_metadata() -> None:
    extracted = ArticleExtractor(min_clean_text_words=20).extract(
        FetchResult(url="https://example.com/article", final_url="https://example.com/article", content_type="text/html", html=ARTICLE_HTML)
    )

    assert extracted.title == "Kubernetes Security Lessons"
    assert "Subscribe Login Pricing" not in extracted.clean_text
    assert "Cookie settings" not in extracted.clean_text
    assert "observability" in extracted.clean_text
    assert extracted.author == "Alex Morgan"
    assert extracted.canonical_url == "https://example.com/canonical"
    assert extracted.publication_date is not None


def test_article_extraction_rejects_tiny_documents() -> None:
    with pytest.raises(ArticleExtractionError):
        ArticleExtractor(min_clean_text_words=20).extract(
            FetchResult(url="https://example.com", final_url="https://example.com", content_type="text/html", html="<p>Too short.</p>")
        )


def test_processor_creates_summary_keywords_tags_and_entities() -> None:
    extracted = ArticleExtractor(min_clean_text_words=20).extract(
        FetchResult(url="https://example.com/article", final_url="https://example.com/article", content_type="text/html", html=ARTICLE_HTML)
    )

    processed = KnowledgeProcessor().process(extracted)

    assert processed.summary
    assert "kubernetes" in processed.keywords
    assert "Cloud Infrastructure" in processed.technology_tags
    assert "Cybersecurity" in processed.technology_tags
    assert "OpenAI" in processed.companies
    assert processed.word_count > 40
    assert processed.reading_time_minutes >= 1


def test_knowledge_service_fetches_extracts_processes_and_persists(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos)

    document = service(repos).build_for_topic(topic_id)

    assert document.topic_id == topic_id
    assert document.version_number == 1
    assert document.title == "Kubernetes Security Lessons"
    assert document.raw_html is not None
    assert document.canonical_url == "https://example.com/canonical"
    assert repos.knowledge.count() == 1


def test_knowledge_repository_preserves_history(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos)
    knowledge = service(repos)

    first = knowledge.build_for_topic(topic_id)
    second = knowledge.build_for_topic(topic_id)

    assert first.id != second.id
    assert first.version_number == 1
    assert second.version_number == 2
    assert len(repos.knowledge.list_for_topic(topic_id)) == 2


def test_knowledge_service_failure_is_visible(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos)

    with pytest.raises(KnowledgeFetchError):
        service(repos, FakeFetcher(fail=True)).build_for_topic(topic_id)

    assert repos.knowledge.count() == 0


def test_build_knowledge_job_executes_through_job_engine(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos)
    handlers = JobHandlerRegistry()
    handlers.register(BUILD_KNOWLEDGE, BuildKnowledgeJobHandler(service(repos)))
    engine = JobExecutionEngine(
        jobs=repos.jobs,
        handlers=handlers,
        retry_policy=RetryPolicy(base_delay=timedelta(seconds=1), backoff_multiplier=2, max_delay=timedelta(seconds=10)),
        metrics=RuntimeMetrics(),
        logger=get_logger("test"),
    )
    job = repos.jobs.create(job_type=BUILD_KNOWLEDGE, payload={"topic_id": topic_id})
    claimed = repos.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)

    assert result.status == JobStatus.COMPLETED
    assert repos.knowledge.count() == 1


def test_build_knowledge_job_requires_topic_id(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    handlers = JobHandlerRegistry()
    handlers.register(BUILD_KNOWLEDGE, BuildKnowledgeJobHandler(service(repos)))
    engine = JobExecutionEngine(
        jobs=repos.jobs,
        handlers=handlers,
        retry_policy=RetryPolicy(base_delay=timedelta(seconds=1), backoff_multiplier=2, max_delay=timedelta(seconds=10)),
        metrics=RuntimeMetrics(),
        logger=get_logger("test"),
    )
    job = repos.jobs.create(job_type=BUILD_KNOWLEDGE, payload={})
    claimed = repos.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)

    assert result.status == JobStatus.RETRYING
    assert repos.knowledge.count() == 0
