from __future__ import annotations

from pathlib import Path
import base64
import io
import json

from content_engine.config import ImageSettings
from content_engine.content_lifecycle.pipeline import PipelineCoordinator
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.domain import ArtifactType, ContentItemStage, Platform, Job
from content_engine.images import (
    GENERATE_IMAGE,
    GenerateImageJobHandler,
    ImageGenerationService,
    ImagePromptBuilder,
    ImageValidator,
    LocalTemplateImageProvider,
    StableDiffusionWebUIImageProvider,
)
from content_engine.images.models import ImageGenerationRequest
from PIL import Image


def build_repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def test_image_prompt_builder_uses_knowledge_and_plan(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_writing_ready_content_item(repositories)
    knowledge = repositories.knowledge.required(
        latest_artifact(repositories, content_item_id, ArtifactType.KNOWLEDGE).artifact_id
    )
    plan = repositories.content_plans.required(latest_artifact(repositories, content_item_id, ArtifactType.PLAN).artifact_id)

    prompt = ImagePromptBuilder(ImageSettings(prompt_version="test")).build(
        content_item_id=content_item_id,
        platform=Platform.LINKEDIN,
        knowledge=knowledge,
        plan=plan,
    )

    assert prompt.prompt_version == "test"
    assert "Clean Startup" in prompt.style_metadata["visual_theme"]
    assert "feedback accelerators" in prompt.positive_prompt
    assert prompt.prompt_hash


def test_local_template_provider_creates_valid_png(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_writing_ready_content_item(repositories)
    service = build_image_service(tmp_path, repositories)

    artifact = service.generate_for_content_item(content_item_id=content_item_id)
    validation = ImageValidator().validate(artifact.file_path, expected_width=1200, expected_height=627)

    assert validation.ok is True
    assert artifact.provider == "local_template"
    assert artifact.model == "local-template-v2"
    assert artifact.file_hash == validation.file_hash
    assert artifact.metadata["file_size_bytes"] > 0


def test_stable_diffusion_webui_provider_calls_txt2img_and_writes_png(tmp_path: Path, monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps({"images": [_encoded_png(width=64, height=64)]}).encode("utf-8")

    def fake_urlopen(http_request, timeout):
        calls.append((http_request, timeout, json.loads(http_request.data.decode("utf-8"))))
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    settings = ImageSettings(
        provider="stable_diffusion_webui",
        model="local-sd-test",
        width=1200,
        height=627,
        stable_diffusion_base_url="http://127.0.0.1:7860",
        stable_diffusion_timeout_seconds=3,
        stable_diffusion_steps=8,
        stable_diffusion_cfg_scale=5.5,
    )
    provider = StableDiffusionWebUIImageProvider(settings=settings)

    result = provider.generate(
        ImageGenerationRequest(
            content_item_id="item-1",
            platform=Platform.LINKEDIN,
            positive_prompt="professional AI infrastructure editorial image",
            negative_prompt="blurry",
            style_metadata={"visual_headline": "Local LLM inference", "image_terms": ["LLM", "GPU"]},
            output_path=tmp_path / "sd.png",
            width=settings.width,
            height=settings.height,
            seed=123,
        )
    )
    validation = ImageValidator().validate(result.file_path, expected_width=1200, expected_height=627)

    assert validation.ok is True
    assert result.provider == "stable_diffusion_webui"
    assert result.model == "local-sd-test"
    assert calls[0][0].full_url == "http://127.0.0.1:7860/sdapi/v1/txt2img"
    assert calls[0][1] == 3
    assert calls[0][2]["steps"] == 8
    assert calls[0][2]["cfg_scale"] == 5.5
    assert calls[0][2]["height"] == 624


def test_image_persistence_and_cache_reuse(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_writing_ready_content_item(repositories)
    service = build_image_service(tmp_path, repositories)

    first = service.generate_for_content_item(content_item_id=content_item_id)
    second = service.generate_for_content_item(content_item_id=content_item_id)

    assert first.file_path == second.file_path
    assert first.file_hash == second.file_hash
    assert second.metadata["cache_hit"] is True
    assert repositories.images.stats().total == 2


def test_generate_image_job_records_artifact_and_advances_lifecycle(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_writing_ready_content_item(repositories)
    pipeline = PipelineCoordinator(repositories)
    handler = GenerateImageJobHandler(build_image_service(tmp_path, repositories), pipeline=pipeline)

    result = handler(Job(id="job-1", job_type=GENERATE_IMAGE, payload={"content_item_id": content_item_id}))
    item = repositories.content_items.required(content_item_id)
    artifacts = repositories.content_items.artifacts_for_item(content_item_id)

    assert result.success is True
    assert item.stage == ContentItemStage.IMAGE_READY
    assert any(artifact.artifact_type == ArtifactType.IMAGE for artifact in artifacts)
    assert repositories.images.stats().total == 1


def build_image_service(tmp_path: Path, repositories: RepositoryRegistry) -> ImageGenerationService:
    settings = ImageSettings(width=1200, height=627, retry_limit=1, reuse_cached_images=True)
    return ImageGenerationService(
        repositories=repositories,
        provider=LocalTemplateImageProvider(model=settings.model),
        prompt_builder=ImagePromptBuilder(settings),
        validator=ImageValidator(),
        settings=settings,
        images_dir=tmp_path / "images",
    )


def create_writing_ready_content_item(repositories: RepositoryRegistry) -> str:
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
    post = repositories.posts.create(
        content_item_id=item.id,
        platform=Platform.LINKEDIN,
        title="Draft",
        hook="A useful hook",
        body="A useful body for a LinkedIn post about AI feedback loops.",
        call_to_action="Where would you keep review?",
        hashtags=("#AI", "#DevTools"),
        estimated_reading_time_seconds=30,
        generation_metadata={"attempts": 1},
        provider_metadata={"provider": "fake"},
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
    repositories.content_items.attach_artifact(
        content_item_id=item.id,
        artifact_type=ArtifactType.POST,
        artifact_id=post.id,
    )
    repositories.content_items.transition(item.id, ContentItemStage.WRITING_READY)
    return item.id


def latest_artifact(repositories: RepositoryRegistry, content_item_id: str, artifact_type: ArtifactType):
    artifacts = [
        artifact
        for artifact in repositories.content_items.artifacts_for_item(content_item_id)
        if artifact.artifact_type == artifact_type
    ]
    assert artifacts
    return artifacts[-1]


def _encoded_png(*, width: int, height: int) -> str:
    image = Image.new("RGB", (width, height), (20, 30, 40))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
