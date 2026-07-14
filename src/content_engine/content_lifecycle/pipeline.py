"""Content pipeline coordination.

The coordinator owns cross-subsystem workflow rules. Discovery, knowledge, and
planning remain focused services; this layer binds their outputs to one
ContentItem and schedules the next durable jobs.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from content_engine.db.repositories import RepositoryRegistry
from content_engine.domain import ArtifactType, ContentArtifact, ContentItem, ContentItemStage, Job, JobStatus
from content_engine.images.jobs import GENERATE_IMAGE
from content_engine.knowledge.jobs import BUILD_KNOWLEDGE
from content_engine.planning.jobs import PLAN_CONTENT
from content_engine.publishing.jobs import PUBLISH_LINKEDIN
from content_engine.writing.jobs import WRITE_LINKEDIN_POST


@dataclass(frozen=True)
class PipelineScheduleResult:
    content_item: ContentItem
    jobs: tuple[Job, ...]


@dataclass(frozen=True)
class PipelineMetrics:
    items_created: int
    stage_distribution: dict[str, int]
    failed_items: int
    average_completion_seconds: float
    queue_size: int
    retrying_jobs: int


class PipelineCoordinator:
    def __init__(self, repositories: RepositoryRegistry, logger: logging.Logger | None = None) -> None:
        self.repositories = repositories
        self.logger = logger or logging.getLogger(__name__)

    def create_content_item_for_topic(self, topic_id: str) -> ContentItem:
        topic = self.repositories.topics.get(topic_id)
        if topic is None:
            raise LookupError(f"Topic not found: {topic_id}")
        content_item = self.repositories.content_items.create(
            title=topic.title,
            source_topic_id=topic.id,
            metadata={"source": topic.source, "provider_name": topic.provider_name},
        )
        self.repositories.content_items.attach_artifact(
            content_item_id=content_item.id,
            artifact_type=ArtifactType.TOPIC,
            artifact_id=topic.id,
        )
        self.logger.info(
            "content_item_created",
            extra={"content_item_id": content_item.id, "topic_id": topic.id, "stage": content_item.stage.value},
        )
        return content_item

    def schedule_pipeline_for_topic(self, topic_id: str) -> PipelineScheduleResult:
        content_item = self.create_content_item_for_topic(topic_id)
        jobs = self.schedule_next_jobs(content_item.id)
        return PipelineScheduleResult(content_item=content_item, jobs=tuple(jobs))

    def schedule_next_jobs(self, content_item_id: str) -> list[Job]:
        content_item = self.repositories.content_items.required(content_item_id)
        if content_item.source_topic_id is None:
            raise ValueError(f"Content item has no source topic: {content_item.id}")
        jobs: list[Job] = []
        if content_item.stage == ContentItemStage.DISCOVERED:
            knowledge_job = self._schedule_job(BUILD_KNOWLEDGE, content_item=content_item)
            plan_job = self._schedule_job(PLAN_CONTENT, content_item=content_item, dependencies=(knowledge_job.id,))
            jobs.extend([knowledge_job, plan_job])
        elif content_item.stage == ContentItemStage.KNOWLEDGE_READY:
            jobs.append(self._schedule_job(PLAN_CONTENT, content_item=content_item))
        elif content_item.stage == ContentItemStage.PLANNED:
            jobs.append(self._schedule_job(WRITE_LINKEDIN_POST, content_item=content_item))
        elif content_item.stage == ContentItemStage.WRITING_READY:
            jobs.append(self._schedule_job(GENERATE_IMAGE, content_item=content_item))
        elif content_item.stage == ContentItemStage.READY_TO_PUBLISH:
            jobs.append(self._schedule_job(PUBLISH_LINKEDIN, content_item=content_item))
        return jobs

    def resume_interrupted_pipelines(self) -> list[PipelineScheduleResult]:
        results: list[PipelineScheduleResult] = []
        for content_item in self._active_items():
            jobs = self.schedule_next_jobs(content_item.id)
            if jobs:
                results.append(PipelineScheduleResult(content_item=content_item, jobs=tuple(jobs)))
        return results

    def record_artifact(
        self,
        *,
        content_item_id: str,
        artifact_type: ArtifactType,
        artifact_id: str,
        job_id: str | None = None,
        metadata: dict | None = None,
        schedule_next: bool = True,
    ) -> ContentArtifact:
        artifact = self.repositories.content_items.attach_artifact(
            content_item_id=content_item_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            metadata=metadata,
        )
        self._advance_for_artifact(content_item_id=content_item_id, artifact_type=artifact_type, job_id=job_id)
        if schedule_next:
            self.schedule_next_jobs(content_item_id)
        return artifact

    def mark_failed(self, content_item_id: str, *, reason: str, job_id: str | None = None) -> ContentItem:
        self.logger.warning(
            "content_item_failed",
            extra={"content_item_id": content_item_id, "job_id": job_id, "reason": reason},
        )
        return self.repositories.content_items.mark_failed(content_item_id, reason=reason, job_id=job_id)

    def metrics(self) -> PipelineMetrics:
        lifecycle_stats = self.repositories.content_items.stats()
        queue_stats = self.repositories.jobs.stats()
        return PipelineMetrics(
            items_created=lifecycle_stats.items_created,
            stage_distribution=lifecycle_stats.stage_distribution,
            failed_items=lifecycle_stats.failed_items,
            average_completion_seconds=lifecycle_stats.average_completion_seconds,
            queue_size=queue_stats.executable + queue_stats.running,
            retrying_jobs=queue_stats.retrying,
        )

    def _schedule_job(
        self,
        job_type: str,
        *,
        content_item: ContentItem,
        dependencies: tuple[str, ...] = (),
    ) -> Job:
        payload = {"topic_id": content_item.source_topic_id, "content_item_id": content_item.id}
        existing = self.repositories.jobs.find_existing(
            job_type=job_type,
            payload=payload,
            statuses=(
                JobStatus.PENDING,
                JobStatus.RETRYING,
                JobStatus.RUNNING,
                JobStatus.COMPLETED,
            ),
        )
        if existing is not None:
            return existing
        job = self.repositories.jobs.create(job_type=job_type, payload=payload, dependencies=list(dependencies))
        self.logger.info(
            "pipeline_job_scheduled",
            extra={"content_item_id": content_item.id, "job_id": job.id, "job_type": job.job_type},
        )
        return job

    def _advance_for_artifact(
        self,
        *,
        content_item_id: str,
        artifact_type: ArtifactType,
        job_id: str | None,
    ) -> None:
        content_item = self.repositories.content_items.required(content_item_id)
        stage_by_artifact = {
            ArtifactType.KNOWLEDGE: ContentItemStage.KNOWLEDGE_READY,
            ArtifactType.PLAN: ContentItemStage.PLANNED,
            ArtifactType.POST: ContentItemStage.WRITING_READY,
            ArtifactType.IMAGE: ContentItemStage.IMAGE_READY,
            ArtifactType.PUBLISHING: ContentItemStage.PUBLISHED,
        }
        next_stage = stage_by_artifact.get(artifact_type)
        if next_stage is None or content_item.stage == next_stage:
            return
        self.repositories.content_items.transition(
            content_item_id,
            next_stage,
            reason=f"{artifact_type.value} artifact recorded",
            job_id=job_id,
        )

    def _active_items(self) -> list[ContentItem]:
        with self.repositories.content_items.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM content_items
                WHERE status = ?
                ORDER BY created_at ASC
                """,
                ("active",),
            ).fetchall()
        return [self.repositories.content_items.required(str(row["id"])) for row in rows]
