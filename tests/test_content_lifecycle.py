from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from content_engine.content_lifecycle.fsm import ContentLifecycleError
from content_engine.content_lifecycle.pipeline import PipelineCoordinator
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.domain import ArtifactType, ContentItemStage, ContentItemStatus, Job, JobStatus
from content_engine.knowledge.jobs import BUILD_KNOWLEDGE, BuildKnowledgeJobHandler
from content_engine.planning.jobs import PLAN_CONTENT, PlanContentJobHandler


def build_repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def create_topic(repositories: RepositoryRegistry, *, title: str = "AI developer tools are changing") -> str:
    topic = repositories.topics.create(
        title=title,
        source="hacker_news",
        summary="A useful technical story.",
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        author="tester",
        score=100,
        provider_name="hacker_news",
        metadata={},
        published_at=None,
        normalized_url=f"https://example.com/{title.lower().replace(' ', '-')}",
        normalized_title=title.lower(),
    )
    assert topic is not None
    return topic.id


def test_content_item_lifecycle_transitions_are_persisted(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    item = repositories.content_items.create(title="AI developer tools are changing", source_topic_id=topic_id)

    updated = repositories.content_items.transition(
        item.id,
        ContentItemStage.KNOWLEDGE_READY,
        reason="knowledge created",
    )
    history = repositories.content_items.stage_history(item.id)

    assert updated.stage == ContentItemStage.KNOWLEDGE_READY
    assert updated.status == ContentItemStatus.ACTIVE
    assert [entry.to_stage for entry in history] == [
        ContentItemStage.DISCOVERED,
        ContentItemStage.KNOWLEDGE_READY,
    ]


def test_invalid_lifecycle_transition_is_rejected(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    item = repositories.content_items.create(title="AI developer tools are changing", source_topic_id=topic_id)

    with pytest.raises(ContentLifecycleError):
        repositories.content_items.transition(item.id, ContentItemStage.PLANNED)


def test_artifacts_are_attached_to_content_items_once(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    item = repositories.content_items.create(title="AI developer tools are changing", source_topic_id=topic_id)

    first = repositories.content_items.attach_artifact(
        content_item_id=item.id,
        artifact_type=ArtifactType.TOPIC,
        artifact_id=topic_id,
    )
    second = repositories.content_items.attach_artifact(
        content_item_id=item.id,
        artifact_type=ArtifactType.TOPIC,
        artifact_id=topic_id,
    )
    artifacts = repositories.content_items.artifacts_for_item(item.id)

    assert first.id == second.id
    assert len(artifacts) == 1
    assert artifacts[0].artifact_type == ArtifactType.TOPIC


def test_job_dependencies_block_execution_until_completed(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    dependency = repositories.jobs.create(job_type=BUILD_KNOWLEDGE, payload={"topic_id": "topic-1"})
    dependent = repositories.jobs.create(
        job_type=PLAN_CONTENT,
        payload={"topic_id": "topic-1"},
        priority=1,
        dependencies=[dependency.id],
    )

    first_claim = repositories.jobs.claim_next(worker_id="worker-a")
    repositories.jobs.mark_completed(dependency.id)
    second_claim = repositories.jobs.claim_next(worker_id="worker-a")

    assert first_claim is not None
    assert first_claim.id == dependency.id
    assert second_claim is not None
    assert second_claim.id == dependent.id
    assert second_claim.dependencies == (dependency.id,)


def test_job_with_unmet_dependency_is_not_claimed(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    repositories.jobs.create(
        job_type=PLAN_CONTENT,
        payload={"topic_id": "topic-1"},
        dependencies=["missing-job"],
    )

    assert repositories.jobs.claim_next(worker_id="worker-a") is None


def test_pipeline_creates_canonical_item_and_avoids_duplicate_jobs(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    coordinator = PipelineCoordinator(repositories)

    first = coordinator.schedule_pipeline_for_topic(topic_id)
    second = coordinator.schedule_pipeline_for_topic(topic_id)
    artifacts = repositories.content_items.artifacts_for_item(first.content_item.id)

    assert first.content_item.id == second.content_item.id
    assert len(first.jobs) == 2
    assert first.jobs[0].job_type == BUILD_KNOWLEDGE
    assert first.jobs[1].job_type == PLAN_CONTENT
    assert first.jobs[1].dependencies == (first.jobs[0].id,)
    assert second.jobs[0].id == first.jobs[0].id
    assert second.jobs[1].id == first.jobs[1].id
    assert artifacts[0].artifact_type == ArtifactType.TOPIC


def test_pipeline_records_artifact_and_resumes_next_stage(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    coordinator = PipelineCoordinator(repositories)
    result = coordinator.schedule_pipeline_for_topic(topic_id)

    coordinator.record_artifact(
        content_item_id=result.content_item.id,
        artifact_type=ArtifactType.KNOWLEDGE,
        artifact_id="knowledge-1",
        job_id=result.jobs[0].id,
    )
    resumed = coordinator.resume_interrupted_pipelines()
    item = repositories.content_items.required(result.content_item.id)

    assert item.stage == ContentItemStage.KNOWLEDGE_READY
    assert len(resumed) == 1
    assert resumed[0].jobs[0].job_type == PLAN_CONTENT
    assert resumed[0].jobs[0].payload["content_item_id"] == item.id


def test_pipeline_failure_is_persisted(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    coordinator = PipelineCoordinator(repositories)
    result = coordinator.schedule_pipeline_for_topic(topic_id)

    failed = coordinator.mark_failed(result.content_item.id, reason="network unavailable", job_id=result.jobs[0].id)

    assert failed.status == ContentItemStatus.FAILED
    assert failed.failure_reason == "network unavailable"
    assert repositories.jobs.stats().pending == 2


def test_knowledge_job_handler_records_lifecycle_artifact(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    coordinator = PipelineCoordinator(repositories)
    item = coordinator.create_content_item_for_topic(topic_id)
    handler = BuildKnowledgeJobHandler(FakeKnowledgeService(), pipeline=coordinator)

    result = handler(Job(id="job-1", job_type=BUILD_KNOWLEDGE, payload={"topic_id": topic_id, "content_item_id": item.id}))
    updated = repositories.content_items.required(item.id)
    artifacts = repositories.content_items.artifacts_for_item(item.id)

    assert result.success is True
    assert updated.stage == ContentItemStage.KNOWLEDGE_READY
    assert any(artifact.artifact_type == ArtifactType.KNOWLEDGE for artifact in artifacts)


def test_planning_job_handler_records_lifecycle_artifact(tmp_path: Path) -> None:
    repositories = build_repositories(tmp_path)
    topic_id = create_topic(repositories)
    coordinator = PipelineCoordinator(repositories)
    item = coordinator.create_content_item_for_topic(topic_id)
    repositories.content_items.transition(item.id, ContentItemStage.KNOWLEDGE_READY)
    handler = PlanContentJobHandler(FakePlanningService(), pipeline=coordinator)

    result = handler(Job(id="job-2", job_type=PLAN_CONTENT, payload={"topic_id": topic_id, "content_item_id": item.id}))
    updated = repositories.content_items.required(item.id)
    artifacts = repositories.content_items.artifacts_for_item(item.id)

    assert result.success is True
    assert updated.stage == ContentItemStage.PLANNED
    assert any(artifact.artifact_type == ArtifactType.PLAN for artifact in artifacts)


class FakeKnowledgeService:
    def build_for_topic(self, topic_id: str):
        return SimpleNamespace(
            id="knowledge-1",
            topic_id=topic_id,
            version_number=1,
            word_count=250,
            keywords=("ai", "developer tools"),
            technology_category="artificial_intelligence",
        )


class FakePlanningService:
    def plan_topic(self, topic_id: str):
        return SimpleNamespace(
            id="plan-1",
            topic_id=topic_id,
            version_number=1,
            writing_persona="Engineer",
            hook_style="Question",
            visual_theme="Clean Startup",
        )
