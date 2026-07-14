from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import logging

from content_engine.app.autopost import AutopostRunner, is_limit_error
from content_engine.app.demo import DemoPipeline, print_demo_report
from content_engine.config import ImageSettings, KnowledgeSettings, PlanningSettings, PublishingSettings, WritingSettings
from content_engine.content_lifecycle.pipeline import PipelineCoordinator
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.discovery import DEFAULT_ALLOWED_CATEGORIES, TopicDiscoveryService, TopicFilter
from content_engine.discovery.deduplication import TopicDeduplicator
from content_engine.discovery.models import TopicCandidate
from content_engine.domain import ArtifactType, ContentItemStage, Platform, TopicStatus
from content_engine.images import ImageGenerationService, ImagePromptBuilder, ImageValidator, LocalTemplateImageProvider
from content_engine.intelligence import ContentIntelligenceService
from content_engine.knowledge.extractor import ArticleExtractor
from content_engine.knowledge.fetcher import ContentFetcher
from content_engine.knowledge.models import FetchResult
from content_engine.knowledge.processor import KnowledgeProcessor
from content_engine.knowledge.service import KnowledgeService
from content_engine.planning import ContentPlanningService, TopicClassifier
from content_engine.publishing import MockPublisher, PublishingService
from content_engine.writing.models import LLMResponse
from content_engine.writing.prompts import PromptRegistry
from content_engine.writing.service import WritingService
from content_engine.writing.writers import LinkedInWriter


def test_demo_pipeline_runs_complete_vertical_slice(tmp_path: Path) -> None:
    container = build_demo_container(tmp_path)

    result = DemoPipeline(container).run_once()
    content_item = container.repositories.content_items.find_by_topic(result.topic.id)
    assert content_item is not None
    artifacts = container.repositories.content_items.artifacts_for_item(content_item.id)

    assert result.topic.status == TopicStatus.SELECTED
    assert content_item.stage == ContentItemStage.IMAGE_READY
    assert {artifact.artifact_type for artifact in artifacts} >= {
        ArtifactType.TOPIC,
        ArtifactType.KNOWLEDGE,
        ArtifactType.PLAN,
        ArtifactType.POST,
        ArtifactType.IMAGE,
    }
    assert container.repositories.knowledge.count() == 1
    assert container.repositories.content_plans.count() == 1
    assert container.repositories.posts.stats().total == 1
    assert container.repositories.images.stats().total == 1
    assert container.repositories.intelligence.stats().experiments == 1
    assert container.repositories.intelligence.stats().lineage_edges == 4
    assert result.image.file_path.exists()
    assert container.repositories.jobs.stats().pending == 0
    assert "feedback" in f"{result.post.hook} {result.post.body}".lower()


def test_demo_report_prints_clean_summary(tmp_path: Path, capsys) -> None:
    result = DemoPipeline(build_demo_container(tmp_path)).run_once()

    print_demo_report(result)
    output = capsys.readouterr().out

    assert "DEMO PIPELINE COMPLETE" in output
    assert "Selected Topic" in output
    assert "Knowledge Summary" in output
    assert "LinkedIn Draft" in output
    assert "LinkedIn Image" in output
    assert "Draft OK" in output
    assert "Image OK" in output


def test_demo_skips_unextractable_high_ranked_topic(tmp_path: Path) -> None:
    container = build_demo_container(tmp_path, provider=MixedQualityTopicProvider(), fetcher=MixedQualityFetcher())

    result = DemoPipeline(container).run_once()
    topics = container.repositories.topics.list_all()
    skipped = [topic for topic in topics if topic.status == TopicStatus.SKIPPED]
    selected = [topic for topic in topics if topic.status == TopicStatus.SELECTED]

    assert result.topic.title == "AI developer tools improve software feedback loops"
    assert len(skipped) == 1
    assert len(selected) == 1
    assert container.repositories.content_items.stats().failed_items == 1
    assert container.repositories.posts.stats().total == 1
    assert container.repositories.images.stats().total == 1
    assert container.repositories.intelligence.stats().experiments == 1


def test_demo_uses_stored_topics_when_discovery_inserts_only_duplicates(tmp_path: Path) -> None:
    container = build_demo_container(tmp_path)
    first = DemoPipeline(container).run_once()

    second = DemoPipeline(container).run_once()

    assert second.topic.id == first.topic.id
    assert container.repositories.topics.count() == 1
    assert container.repositories.posts.stats().total == 1
    assert container.repositories.images.stats().total == 1


def test_autopost_runner_publishes_one_iteration(tmp_path: Path) -> None:
    container = build_demo_container(tmp_path)
    container.publishing = PublishingService(
        repositories=container.repositories,
        publisher=MockPublisher(),
        publishing_settings=PublishingSettings(
            linkedin_session_dir=tmp_path / "browser",
            screenshot_dir=tmp_path / "screenshots",
            linkedin_author_name="Owner",
            linkedin_target_page_name="Example Page",
        ),
        runtime_settings=SimpleNamespace(dry_run=False),
    )
    runner = AutopostRunner(container, delay_seconds=0, max_posts=1)

    result = runner.run_forever()

    assert result.published == 1
    assert container.repositories.publications.stats().published == 1
    assert container.repositories.content_items.stats().stage_distribution["published"] == 1


def test_autopost_detects_limit_errors() -> None:
    assert is_limit_error(RuntimeError("OpenRouter generation failed: HTTP Error 402: Payment Required"))
    assert is_limit_error(RuntimeError("HTTP Error 429: rate limit exceeded"))
    assert not is_limit_error(RuntimeError("Extracted article text is too short"))


class FakeTopicProvider:
    def discover_topics(self) -> list[TopicCandidate]:
        return [
            TopicCandidate(
                title="AI developer tools improve software feedback loops",
                url="https://example.com/ai-feedback",
                source="hacker_news",
                provider_name="fake_hacker_news",
                description="A practical software engineering article about AI developer tools and feedback loops.",
                author="tester",
                score=125,
                metadata={"hacker_news_id": 1},
            ),
            TopicCandidate(
                title="Gardening notes for summer",
                url="https://example.com/gardening",
                source="hacker_news",
                provider_name="fake_hacker_news",
                description="Not a technology topic.",
                author="tester",
                score=500,
                metadata={"hacker_news_id": 2},
            ),
        ]


class MixedQualityTopicProvider:
    def discover_topics(self) -> list[TopicCandidate]:
        return [
            TopicCandidate(
                title="AI launch page with no article text",
                url="https://example.com/too-short",
                source="hacker_news",
                provider_name="fake_hacker_news",
                description="A software AI announcement with a sparse landing page.",
                author="tester",
                score=300,
                metadata={"hacker_news_id": 100},
            ),
            TopicCandidate(
                title="AI developer tools improve software feedback loops",
                url="https://example.com/ai-feedback",
                source="hacker_news",
                provider_name="fake_hacker_news",
                description="A practical software engineering article about AI developer tools and feedback loops.",
                author="tester",
                score=125,
                metadata={"hacker_news_id": 1},
            ),
        ]


class FakeFetcher(ContentFetcher):
    def fetch(self, url: str) -> FetchResult:
        paragraphs = " ".join(
            [
                "AI developer tools are becoming useful because they shorten feedback loops for engineering teams.",
                "The strongest teams still keep humans responsible for architecture, review, and production judgment.",
                "The practical value comes from faster tests, clearer diffs, better explanations, and earlier visibility into weak assumptions.",
                "This matters for software engineering leaders because speed without review can increase risk, while feedback-centered workflows improve quality.",
                "A measured adoption strategy treats AI as a feedback accelerator rather than a replacement for engineering responsibility.",
            ]
            * 4
        )
        return FetchResult(
            url=url,
            final_url=url,
            content_type="text/html",
            html=f"<html><head><title>AI feedback loops</title></head><body><article><h1>AI feedback loops</h1><p>{paragraphs}</p></article></body></html>",
            status_code=200,
        )


class MixedQualityFetcher(FakeFetcher):
    def fetch(self, url: str) -> FetchResult:
        if url.endswith("/too-short"):
            return FetchResult(
                url=url,
                final_url=url,
                content_type="text/html",
                html="<html><body><article><p>Too short.</p></article></body></html>",
                status_code=200,
            )
        return super().fetch(url)


class FakeLLMProvider:
    metadata = SimpleNamespace(name="fake_llm", provider_type="llm", requires_network=False)

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, request):
        self.calls += 1
        if self.calls == 1:
            hook = "AI developer tools are most useful when they make feedback faster, not when they replace engineering judgment."
            body = "The interesting shift is not that teams can produce more code. It is that review, testing, and architectural trade-offs can surface earlier. Engineers get a better chance to catch weak assumptions while the work is still cheap to change. Strong teams design workflows around visibility, judgment, and clear ownership instead of blind acceleration."
        else:
            hook = "The useful question is not whether AI writes code. It is whether the team learns sooner."
            body = "A healthier adoption pattern starts with small reviewable changes, fast tests, and explicit ownership. AI can help explain unfamiliar code, draft alternatives, and reveal assumptions, but engineers still need to decide what belongs in the system. That makes the workflow less about volume and more about reducing uncertainty before expensive decisions harden."
        return LLMResponse(
            text=f"""
            {{
              "title": "AI feedback loops",
              "hook": "{hook}",
              "body": "{body}",
              "call_to_action": "Where would you keep the human checkpoint in this workflow?",
              "hashtags": ["#AI", "#DevTools", "#SoftwareEngineering"]
            }}
            """,
            provider_name="fake_llm",
            model="fake-model",
            token_usage={"prompt_tokens": 120, "completion_tokens": 140},
        )


def build_demo_container(tmp_path: Path, provider=None, fetcher=None):
    database = Database(tmp_path / "demo.sqlite3")
    MigrationRunner(database).apply()
    repositories = RepositoryRegistry.create(database)
    logger = logging.getLogger(f"demo-test-{tmp_path.name}")
    logger.addHandler(logging.NullHandler())

    discovery = TopicDiscoveryService(
        providers=[provider or FakeTopicProvider()],
        topic_filter=TopicFilter(DEFAULT_ALLOWED_CATEGORIES),
        deduplicator=TopicDeduplicator(repositories.topics, title_similarity_threshold=0.88),
        topics=repositories.topics,
        logger=logger,
    )
    knowledge = KnowledgeService(
        topics=repositories.topics,
        knowledge=repositories.knowledge,
        fetcher=fetcher or FakeFetcher(),
        extractor=ArticleExtractor(min_clean_text_words=30),
        processor=KnowledgeProcessor(),
        settings=KnowledgeSettings(min_clean_text_words=30, store_raw_html=True),
        logger=logger,
    )
    planning = ContentPlanningService(
        topics=repositories.topics,
        plans=repositories.content_plans,
        settings=PlanningSettings(),
        classifier=TopicClassifier(),
        logger=logger,
    )
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "system.md").write_text("<!-- version: test -->System {writing_persona}", encoding="utf-8")
    (prompt_dir / "linkedin.md").write_text(
        "<!-- version: test -->Write {content_item_title} {knowledge_summary} {validation_feedback}",
        encoding="utf-8",
    )
    writing_settings = WritingSettings(
        prompt_dir=prompt_dir,
        min_post_characters=120,
        max_post_characters=2_000,
        banned_phrases=("game changer", "unlock the power"),
        max_hashtags=3,
    )
    writer = LinkedInWriter(
        provider=FakeLLMProvider(),
        prompts=PromptRegistry(prompt_dir),
        posts=repositories.posts,
        settings=writing_settings,
    )
    image_settings = ImageSettings()
    return SimpleNamespace(
        logger=logger,
        repositories=repositories,
        topic_discovery=discovery,
        pipeline=PipelineCoordinator(repositories, logger=logger),
        knowledge=knowledge,
        content_planning=planning,
        writing=WritingService(repositories=repositories, writers=[writer], logger=logger),
        image_generation=ImageGenerationService(
            repositories=repositories,
            provider=LocalTemplateImageProvider(model=image_settings.model),
            prompt_builder=ImagePromptBuilder(image_settings),
            validator=ImageValidator(),
            settings=image_settings,
            images_dir=tmp_path / "images",
            logger=logger,
        ),
        content_intelligence=ContentIntelligenceService(
            repositories=repositories,
            settings=SimpleNamespace(
                app=SimpleNamespace(name="test", environment="test"),
                storage=SimpleNamespace(root_dir=str(tmp_path)),
                database=SimpleNamespace(path=str(tmp_path / "demo.sqlite3")),
                logging=SimpleNamespace(level="INFO"),
                runtime=SimpleNamespace(dry_run=True),
                discovery=SimpleNamespace(enabled_topic_providers=("fake",)),
                planning=SimpleNamespace(),
                knowledge=SimpleNamespace(),
                writing=SimpleNamespace(openrouter_api_key=None, openrouter_model="fake-model"),
                image=SimpleNamespace(provider="local_template", model="local-template-v1"),
            ),
            logger=logger,
        ),
    )
