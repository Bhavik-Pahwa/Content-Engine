from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from content_engine.app.reports import build_report
from content_engine.content_lifecycle.pipeline import PipelineCoordinator
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.domain import ArtifactType, ContentItemStage, Platform
from content_engine.images import ImageGenerationService, ImagePromptBuilder, ImageValidator, LocalTemplateImageProvider
from content_engine.config import ImageSettings
from content_engine.intelligence import ContentIntelligenceService, ContentScorer
from tests.test_images import create_writing_ready_content_item


def build_repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def test_experiment_lineage_metrics_and_score_are_recorded(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_image_ready_content_item(tmp_path, repositories)
    service = ContentIntelligenceService(repositories=repositories, settings=fake_settings(tmp_path))

    record = service.record_for_content_item(content_item_id, notes="test")
    stats = repositories.intelligence.stats()

    assert record.experiment.persona == "Engineer"
    assert record.experiment.hook == "Bold Statement"
    assert record.experiment.visual_theme == "Clean Startup"
    assert record.experiment.image_provider == "local_template"
    assert record.score.score > 0
    assert stats.experiments == 1
    assert stats.lineage_edges == 4
    assert stats.metrics_placeholders == 1
    assert stats.scored_artifacts == 1


def test_intelligence_recording_is_idempotent_for_same_artifacts(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_image_ready_content_item(tmp_path, repositories)
    service = ContentIntelligenceService(repositories=repositories, settings=fake_settings(tmp_path))

    first = service.record_for_content_item(content_item_id)
    second = service.record_for_content_item(content_item_id)

    assert first.experiment.id == second.experiment.id
    assert repositories.intelligence.stats().experiments == 1
    assert repositories.intelligence.stats().lineage_edges == 4


def test_content_scorer_returns_deterministic_metrics(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_writing_ready_content_item(repositories)
    post = repositories.posts.latest_for_content_item(content_item_id, Platform.LINKEDIN)
    assert post is not None

    score = ContentScorer().score_post(post)

    assert score.score > 0
    assert score.paragraph_count >= 1
    assert score.hashtag_count == 2
    assert score.metadata["character_count"] > 0


def test_cli_reports_render_asset_experiment_pipeline_and_statistics(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_image_ready_content_item(tmp_path, repositories)
    service = ContentIntelligenceService(repositories=repositories, settings=fake_settings(tmp_path))
    experiment = service.record_for_content_item(content_item_id).experiment
    container = SimpleNamespace(repositories=repositories)

    latest = build_report(container, command="show-latest-asset")
    experiment_report = build_report(container, command="show-experiment", identifier=experiment.id)
    pipeline = build_report(container, command="show-pipeline", identifier=content_item_id)
    statistics = build_report(container, command="show-statistics")
    listing = build_report(container, command="list-assets", limit=5)

    assert any("Latest Asset" in line for line in latest.lines)
    assert any("Persona: Engineer" in line for line in experiment_report.lines)
    assert any("topic_to_knowledge" in line for line in pipeline.lines)
    assert any("Experiments: 1" in line for line in statistics.lines)
    assert any(content_item_id in line for line in listing.lines)


def create_image_ready_content_item(tmp_path: Path, repositories: RepositoryRegistry) -> str:
    content_item_id = create_writing_ready_content_item(repositories)
    item = repositories.content_items.required(content_item_id)
    assert item.source_topic_id is not None
    repositories.content_items.attach_artifact(
        content_item_id=content_item_id,
        artifact_type=ArtifactType.TOPIC,
        artifact_id=item.source_topic_id,
    )
    settings = ImageSettings(width=1200, height=627)
    image_service = ImageGenerationService(
        repositories=repositories,
        provider=LocalTemplateImageProvider(model=settings.model),
        prompt_builder=ImagePromptBuilder(settings),
        validator=ImageValidator(),
        settings=settings,
        images_dir=tmp_path / "images",
    )
    image = image_service.generate_for_content_item(content_item_id=content_item_id)
    PipelineCoordinator(repositories).record_artifact(
        content_item_id=content_item_id,
        artifact_type=ArtifactType.IMAGE,
        artifact_id=image.id,
        schedule_next=False,
    )
    assert repositories.content_items.required(content_item_id).stage == ContentItemStage.IMAGE_READY
    return content_item_id


def fake_settings(tmp_path: Path):
    return SimpleNamespace(
        app=SimpleNamespace(name="test", environment="test"),
        storage=SimpleNamespace(root_dir=str(tmp_path)),
        database=SimpleNamespace(path=str(tmp_path / "test.sqlite3")),
        logging=SimpleNamespace(level="INFO"),
        runtime=SimpleNamespace(dry_run=True),
        discovery=SimpleNamespace(enabled_topic_providers=("fake",)),
        planning=SimpleNamespace(),
        knowledge=SimpleNamespace(),
        writing=SimpleNamespace(openrouter_api_key=None, openrouter_model="fake-model"),
        image=SimpleNamespace(provider="local_template", model="local-template-v1"),
    )
