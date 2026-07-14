from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

from content_engine.config import PlanningSettings
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.discovery.normalization import normalize_title, normalize_url
from content_engine.domain import JobStatus
from content_engine.observability import get_logger
from content_engine.orchestration import JobExecutionEngine, JobHandlerRegistry, RetryPolicy, RuntimeMetrics
from content_engine.planning import PLAN_CONTENT, ContentPlanningService, PlanContentJobHandler, TopicClassifier


def repositories(tmp_path: Path) -> RepositoryRegistry:
    database = Database(tmp_path / "test.sqlite3")
    MigrationRunner(database).apply()
    return RepositoryRegistry.create(database)


def create_topic(repos: RepositoryRegistry, title: str = "Kubernetes security lessons for platform teams") -> str:
    normalized_title = normalize_title(title)
    normalized_url = normalize_url("https://example.com/topic")
    topic = repos.topics.create(
        title=title,
        source="test",
        summary="A practical look at cloud security and software architecture.",
        url="https://example.com/topic",
        author="alice",
        score=100,
        provider_name="test_provider",
        metadata={"source_test": True},
        published_at=datetime.now(timezone.utc),
        normalized_url=normalized_url,
        normalized_title=normalized_title,
    )
    assert topic is not None
    return topic.id


def planner(repos: RepositoryRegistry, settings: PlanningSettings | None = None) -> ContentPlanningService:
    return ContentPlanningService(
        topics=repos.topics,
        plans=repos.content_plans,
        settings=settings or PlanningSettings(),
        classifier=TopicClassifier(),
        logger=get_logger("test"),
    )


def test_topic_classifier_extracts_category_keywords_and_difficulty(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos, "Database internals for distributed systems")
    topic = repos.topics.get(topic_id)
    assert topic is not None

    classification = TopicClassifier().classify(topic)

    assert classification.category == "Software Engineering"
    assert classification.difficulty_level == "advanced"
    assert "database" in classification.keywords


def test_planner_creates_platform_independent_content_plan(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos)
    service = planner(
        repos,
        PlanningSettings(
            enabled_personas=("Engineer", "Educator"),
            hook_styles=("Question", "Tutorial"),
            visual_themes=("Blueprint", "Minimal Tech"),
            future_platform_targets=("linkedin", "blog"),
        ),
    )

    plan = service.plan_topic(topic_id)

    assert plan.topic_id == topic_id
    assert plan.version_number == 1
    assert plan.writing_persona == "Engineer"
    assert plan.visual_theme in {"Blueprint", "Minimal Tech"}
    assert plan.platform_targets == ("linkedin", "blog")
    assert "LinkedIn text" not in plan.primary_angle
    assert "caption" not in plan.primary_angle.lower()
    assert repos.content_plans.count() == 1


def test_planner_preserves_history_with_new_versions(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos)
    service = planner(repos)

    first = service.plan_topic(topic_id)
    second = service.plan_topic(topic_id)
    plans = repos.content_plans.list_for_topic(topic_id)

    assert first.id != second.id
    assert first.version_number == 1
    assert second.version_number == 2
    assert len(plans) == 2


def test_hook_selection_rotates_for_replanned_topic(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos, "Python developer tools for testing")
    service = planner(repos, PlanningSettings(hook_styles=("Question", "Tutorial", "Mistake")))

    first = service.plan_topic(topic_id)
    second = service.plan_topic(topic_id)

    assert first.hook_style != second.hook_style


def test_plan_content_job_executes_through_job_engine(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    topic_id = create_topic(repos)
    handlers = JobHandlerRegistry()
    handlers.register(PLAN_CONTENT, PlanContentJobHandler(planner(repos)))
    engine = JobExecutionEngine(
        jobs=repos.jobs,
        handlers=handlers,
        retry_policy=RetryPolicy(base_delay=timedelta(seconds=1), backoff_multiplier=2, max_delay=timedelta(seconds=10)),
        metrics=RuntimeMetrics(),
        logger=get_logger("test"),
    )
    job = repos.jobs.create(job_type=PLAN_CONTENT, payload={"topic_id": topic_id})
    claimed = repos.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)

    assert result.status == JobStatus.COMPLETED
    assert repos.content_plans.count() == 1


def test_plan_content_job_requires_topic_id(tmp_path: Path) -> None:
    repos = repositories(tmp_path)
    handlers = JobHandlerRegistry()
    handlers.register(PLAN_CONTENT, PlanContentJobHandler(planner(repos)))
    engine = JobExecutionEngine(
        jobs=repos.jobs,
        handlers=handlers,
        retry_policy=RetryPolicy(base_delay=timedelta(seconds=1), backoff_multiplier=2, max_delay=timedelta(seconds=10)),
        metrics=RuntimeMetrics(),
        logger=get_logger("test"),
    )
    job = repos.jobs.create(job_type=PLAN_CONTENT, payload={})
    claimed = repos.jobs.claim_next(worker_id="worker-a")
    assert claimed is not None

    result = engine.execute(claimed)

    assert result.status == JobStatus.RETRYING
    assert repos.content_plans.count() == 0
