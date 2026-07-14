from __future__ import annotations

from pathlib import Path

import pytest

from content_engine.config import PublishingSettings, RuntimeSettings
from content_engine.content_lifecycle.pipeline import PipelineCoordinator
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.domain import ArtifactType, ContentItemStage, Platform, PublishingStatus
from content_engine.publishing import MockPublisher, PUBLISH_LINKEDIN, PublishLinkedInJobHandler, PublishingService
from content_engine.publishing.models import PublishResult
from tests.test_intelligence import create_image_ready_content_item
from content_engine.domain import Job


def build_repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def test_publish_dry_run_records_skipped_attempt_without_advancing_lifecycle(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_ready_to_publish_item(tmp_path, repositories)
    service = build_service(tmp_path, repositories, runtime=RuntimeSettings(dry_run=True), publisher=MockPublisher())

    artifact = service.publish_content_item(content_item_id, platform=Platform.LINKEDIN)
    item = repositories.content_items.required(content_item_id)

    assert artifact.status == PublishingStatus.SKIPPED
    assert artifact.screenshot_before_path is not None
    assert artifact.screenshot_before_path.exists()
    assert item.stage == ContentItemStage.READY_TO_PUBLISH


def test_publish_job_records_publication_and_advances_lifecycle(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_ready_to_publish_item(tmp_path, repositories)
    service = build_service(tmp_path, repositories, runtime=RuntimeSettings(dry_run=False), publisher=MockPublisher())
    handler = PublishLinkedInJobHandler(service, pipeline=PipelineCoordinator(repositories))

    result = handler(Job(id="job-1", job_type=PUBLISH_LINKEDIN, payload={"content_item_id": content_item_id}))
    item = repositories.content_items.required(content_item_id)
    artifacts = repositories.content_items.artifacts_for_item(content_item_id)

    assert result.success is True
    assert result.metadata["status"] == "published"
    assert item.stage == ContentItemStage.PUBLISHED
    assert any(artifact.artifact_type == ArtifactType.PUBLISHING for artifact in artifacts)
    assert repositories.publications.stats().published == 1


def test_publish_is_idempotent_after_success(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_ready_to_publish_item(tmp_path, repositories)
    publisher = CountingPublisher()
    service = build_service(tmp_path, repositories, runtime=RuntimeSettings(dry_run=False), publisher=publisher)

    first = service.publish_content_item(content_item_id, platform=Platform.LINKEDIN)
    second = service.publish_content_item(content_item_id, platform=Platform.LINKEDIN)

    assert first.id == second.id
    assert publisher.calls == 1
    assert repositories.publications.stats().published == 1


def test_publish_failure_records_attempt_and_preserves_ready_state(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_ready_to_publish_item(tmp_path, repositories)
    service = build_service(tmp_path, repositories, runtime=RuntimeSettings(dry_run=False), publisher=FailingPublisher())

    with pytest.raises(Exception):
        service.publish_content_item(content_item_id, platform=Platform.LINKEDIN)

    item = repositories.content_items.required(content_item_id)
    latest = repositories.publications.latest_for_content_item(content_item_id, Platform.LINKEDIN)
    assert latest is not None
    assert latest.status == PublishingStatus.FAILED
    assert item.stage == ContentItemStage.READY_TO_PUBLISH


def test_publish_passes_linkedin_page_target_to_provider(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_ready_to_publish_item(tmp_path, repositories)
    publisher = SpyPublisher()
    service = PublishingService(
        repositories=repositories,
        publisher=publisher,
        publishing_settings=PublishingSettings(
            linkedin_session_dir=tmp_path / "browser",
            screenshot_dir=tmp_path / "screenshots",
            linkedin_author_name="Account Owner",
            linkedin_target_page_name="Example Page",
        ),
        runtime_settings=RuntimeSettings(dry_run=False),
    )

    service.publish_content_item(content_item_id, platform=Platform.LINKEDIN)

    assert publisher.request is not None
    assert publisher.request.linkedin_author_name == "Account Owner"
    assert publisher.request.linkedin_target_page_name == "Example Page"


def test_publish_passes_headless_setting_to_provider(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    content_item_id = create_ready_to_publish_item(tmp_path, repositories)
    publisher = SpyPublisher()
    service = PublishingService(
        repositories=repositories,
        publisher=publisher,
        publishing_settings=PublishingSettings(
            linkedin_session_dir=tmp_path / "browser",
            screenshot_dir=tmp_path / "screenshots",
            headless=False,
        ),
        runtime_settings=RuntimeSettings(dry_run=False),
    )

    service.publish_content_item(content_item_id, platform=Platform.LINKEDIN)

    assert publisher.request is not None
    assert publisher.request.headless is False


def create_ready_to_publish_item(tmp_path: Path, repositories: RepositoryRegistry) -> str:
    content_item_id = create_image_ready_content_item(tmp_path, repositories)
    repositories.content_items.transition(
        content_item_id,
        ContentItemStage.READY_TO_PUBLISH,
        reason="test approval",
    )
    return content_item_id


def build_service(tmp_path: Path, repositories: RepositoryRegistry, *, runtime: RuntimeSettings, publisher) -> PublishingService:
    return PublishingService(
        repositories=repositories,
        publisher=publisher,
        publishing_settings=PublishingSettings(
            linkedin_session_dir=tmp_path / "browser",
            screenshot_dir=tmp_path / "screenshots",
        ),
        runtime_settings=runtime,
    )


class CountingPublisher(MockPublisher):
    def __init__(self) -> None:
        self.calls = 0

    def publish(self, request):
        self.calls += 1
        return super().publish(request)


class FailingPublisher(MockPublisher):
    def publish(self, request):
        raise RuntimeError("simulated LinkedIn outage")


class SpyPublisher(MockPublisher):
    def __init__(self) -> None:
        self.request = None

    def publish(self, request):
        self.request = request
        return super().publish(request)
