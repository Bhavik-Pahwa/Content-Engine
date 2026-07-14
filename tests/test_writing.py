from __future__ import annotations

from pathlib import Path

from content_engine.config import WritingSettings
from content_engine.content_lifecycle.pipeline import PipelineCoordinator
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.domain import ArtifactType, ContentItemStage, Platform, Job
from content_engine.writing.humanizer import PostHumanizer
from content_engine.writing.jobs import WRITE_LINKEDIN_POST, WriteLinkedInPostJobHandler
from content_engine.writing.models import GeneratedPost, LLMResponse
from content_engine.writing.prompts import PromptRegistry
from content_engine.writing.service import WritingService
from content_engine.writing.validation import PostValidator
from content_engine.writing.writers import LinkedInWriter


def build_repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def writing_settings(prompt_dir: Path) -> WritingSettings:
    return WritingSettings(
        prompt_dir=prompt_dir,
        min_post_characters=120,
        max_post_characters=2_000,
        banned_phrases=("game changer", "unlock the power"),
        max_hashtags=3,
    )


def test_prompt_registry_renders_versioned_prompt(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "sample.md").write_text("<!-- version: 2 -->Hello {name}\n{items}", encoding="utf-8")

    rendered = PromptRegistry(prompt_dir).render("sample", {"name": "Ada", "items": ("one", "two")})

    assert rendered.version == "2"
    assert "Hello Ada" in rendered.text
    assert "- one" in rendered.text


def test_humanizer_removes_cliches_and_limits_hashtags(tmp_path: Path) -> None:
    humanizer = PostHumanizer(writing_settings(tmp_path))
    post = GeneratedPost(
        title=" Test ",
        hook="This is a game changer",
        body="Unlock the power of better tooling. Teams need clearer feedback loops.",
        call_to_action="What would you change?",
        hashtags=("#AI", "developer tools", "#AI", "#LongExtra"),
    )

    result = humanizer.humanize(post)

    assert "game changer" not in result.hook.lower()
    assert "unlock the power" not in result.body.lower()
    assert result.hashtags == ("#AI", "#developertools", "#LongExtra")


def test_validator_rejects_short_and_banned_posts(tmp_path: Path) -> None:
    validator = PostValidator(writing_settings(tmp_path))
    post = GeneratedPost(
        title="Tiny",
        hook="A game changer",
        body="Too short.",
        call_to_action="Thoughts?",
        hashtags=("#AI",),
    )

    result = validator.validate(post, platform=Platform.LINKEDIN)

    assert result.ok is False
    assert "post is below minimum length" in result.failures
    assert any("banned phrase" in failure for failure in result.failures)


def test_post_artifact_persistence_versions_history(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_planned_content_item(repositories)

    first = repositories.posts.create(
        content_item_id=content_item_id,
        platform=Platform.LINKEDIN,
        title="Draft 1",
        hook="A useful hook",
        body="A useful body",
        call_to_action="What do you think?",
        hashtags=("#AI",),
        estimated_reading_time_seconds=30,
        generation_metadata={"attempts": 1},
        provider_metadata={"provider": "fake"},
    )
    second = repositories.posts.create(
        content_item_id=content_item_id,
        platform=Platform.LINKEDIN,
        title="Draft 2",
        hook="Another useful hook",
        body="Another useful body",
        call_to_action="What would you try?",
        hashtags=("#DevTools",),
        estimated_reading_time_seconds=35,
        generation_metadata={"attempts": 1},
        provider_metadata={"provider": "fake"},
    )

    assert first.version_number == 1
    assert second.version_number == 2
    assert repositories.posts.latest_for_content_item(content_item_id, Platform.LINKEDIN).id == second.id


def test_linkedin_writer_persists_valid_draft(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_planned_content_item(repositories)
    service = build_writing_service(tmp_path, repositories, FakeProvider())

    post = service.write(content_item_id=content_item_id, platform=Platform.LINKEDIN)

    assert post.platform == Platform.LINKEDIN
    assert post.version_number == 1
    assert post.title == "AI tooling feedback loops"
    assert "#DevTools" in post.hashtags
    assert post.provider_metadata["provider"] == "fake_llm"
    assert post.generation_metadata["generation_duration_seconds"] >= 0


def test_write_linkedin_job_records_post_artifact_and_advances_lifecycle(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_planned_content_item(repositories)
    pipeline = PipelineCoordinator(repositories)
    service = build_writing_service(tmp_path, repositories, FakeProvider())
    handler = WriteLinkedInPostJobHandler(service, pipeline=pipeline)

    result = handler(Job(id="job-1", job_type=WRITE_LINKEDIN_POST, payload={"content_item_id": content_item_id}))
    item = repositories.content_items.required(content_item_id)
    artifacts = repositories.content_items.artifacts_for_item(content_item_id)

    assert result.success is True
    assert item.stage == ContentItemStage.WRITING_READY
    assert any(artifact.artifact_type == ArtifactType.POST for artifact in artifacts)
    assert repositories.posts.stats().total == 1


class FakeProvider:
    metadata = type(
        "Metadata",
        (),
        {"name": "fake_llm", "provider_type": "llm", "requires_network": False},
    )()

    def generate(self, request):
        return LLMResponse(
            text="""
            {
              "title": "AI tooling feedback loops",
              "hook": "The best developer tools do not replace judgment. They shorten the distance to feedback.",
              "body": "That distinction matters for teams adopting AI coding systems. Faster output is useful, but the real advantage appears when review, testing, and architecture decisions become easier to see. A strong workflow keeps engineers in control while using automation to expose trade-offs sooner. It also helps teams notice weak assumptions before they become production problems.",
              "call_to_action": "Where would you put the human review checkpoint?",
              "hashtags": ["#AI", "#DevTools", "#SoftwareEngineering"]
            }
            """,
            provider_name="fake_llm",
            model="fake-model",
            token_usage={"prompt_tokens": 100, "completion_tokens": 120},
        )


def build_writing_service(tmp_path: Path, repositories: RepositoryRegistry, provider: FakeProvider) -> WritingService:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir(exist_ok=True)
    (prompt_dir / "system.md").write_text("<!-- version: test -->System {writing_persona}", encoding="utf-8")
    (prompt_dir / "linkedin.md").write_text(
        "<!-- version: test -->Write {content_item_title} {validation_feedback}",
        encoding="utf-8",
    )
    settings = writing_settings(prompt_dir)
    writer = LinkedInWriter(provider=provider, prompts=PromptRegistry(prompt_dir), posts=repositories.posts, settings=settings)
    return WritingService(repositories=repositories, writers=[writer])


def create_planned_content_item(repositories: RepositoryRegistry) -> str:
    topic = repositories.topics.create(
        title="AI tooling feedback loops",
        source="hacker_news",
        summary="A technical story about AI developer tools.",
        url="https://example.com/ai-tools",
        author="tester",
        score=100,
        provider_name="hacker_news",
        metadata={},
        published_at=None,
        normalized_url="https://example.com/ai-tools",
        normalized_title="ai tooling feedback loops",
    )
    assert topic is not None
    item = repositories.content_items.create(title=topic.title, source_topic_id=topic.id)
    knowledge = repositories.knowledge.create(
        topic_id=topic.id,
        title=topic.title,
        summary="AI developer tools are most useful when they shorten feedback loops without removing human review.",
        clean_text="AI developer tools are most useful when they shorten feedback loops without removing human review.",
        keywords=("ai", "developer tools", "feedback"),
        named_entities=(),
        technology_tags=("AI", "Developer Tools"),
        companies=(),
        people=(),
        concepts=("feedback loops", "human review"),
        source_url="https://example.com/ai-tools",
        canonical_url=None,
        author=None,
        publication_date=None,
        word_count=120,
        language="en",
        reading_time_minutes=1,
        reading_difficulty="intermediate",
        estimated_audience="engineers",
        technology_category="developer_tools",
        raw_html=None,
        metadata={},
    )
    plan = repositories.content_plans.create(
        topic_id=topic.id,
        primary_angle="AI tools work best as feedback accelerators, not replacements for engineering judgment.",
        target_audience="software engineers",
        content_goal="teach",
        content_type="insight",
        hook_style="Bold Statement",
        writing_persona="Engineer",
        visual_theme="Clean Startup",
        image_prompt="A clean interface showing feedback loops",
        video_prompt=None,
        key_points=("Faster output is not the whole value.", "Review checkpoints still matter."),
        call_to_action="Ask readers where they keep human review.",
        platform_targets=("linkedin",),
        metadata={},
    )
    repositories.content_items.attach_artifact(
        content_item_id=item.id,
        artifact_type=ArtifactType.KNOWLEDGE,
        artifact_id=knowledge.id,
    )
    repositories.content_items.transition(item.id, ContentItemStage.KNOWLEDGE_READY)
    repositories.content_items.attach_artifact(
        content_item_id=item.id,
        artifact_type=ArtifactType.PLAN,
        artifact_id=plan.id,
    )
    repositories.content_items.transition(item.id, ContentItemStage.PLANNED)
    return item.id
