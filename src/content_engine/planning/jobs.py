"""Job handlers for content planning."""

from __future__ import annotations

from typing import Any

from content_engine.domain import ArtifactType
from content_engine.domain import Job
from content_engine.orchestration import JobResult
from content_engine.planning.service import ContentPlanningService


PLAN_CONTENT = "PLAN_CONTENT"


class PlanContentJobHandler:
    def __init__(self, planner: ContentPlanningService, pipeline: Any | None = None) -> None:
        self.planner = planner
        self.pipeline = pipeline

    def __call__(self, job: Job) -> JobResult:
        topic_id = job.payload.get("topic_id")
        if not isinstance(topic_id, str) or not topic_id.strip():
            return JobResult(success=False, message="PLAN_CONTENT requires payload.topic_id")
        plan = self.planner.plan_topic(topic_id.strip())
        content_item_id = job.payload.get("content_item_id")
        if self.pipeline is not None and isinstance(content_item_id, str) and content_item_id.strip():
            self.pipeline.record_artifact(
                content_item_id=content_item_id.strip(),
                artifact_type=ArtifactType.PLAN,
                artifact_id=plan.id,
                job_id=job.id,
            )
        return JobResult(
            success=True,
            message=f"planned topic {topic_id}",
            metadata={
                "plan_id": plan.id,
                "topic_id": plan.topic_id,
                "version_number": plan.version_number,
                "persona": plan.writing_persona,
                "hook_style": plan.hook_style,
                "visual_theme": plan.visual_theme,
            },
        )
