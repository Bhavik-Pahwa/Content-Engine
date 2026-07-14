"""Job handlers for the Writing Engine."""

from __future__ import annotations

from typing import Any

from content_engine.domain import ArtifactType, Job, Platform
from content_engine.orchestration import JobResult
from content_engine.writing.service import WritingService


WRITE_LINKEDIN_POST = "WRITE_LINKEDIN_POST"


class WriteLinkedInPostJobHandler:
    def __init__(self, writing: WritingService, pipeline: Any | None = None) -> None:
        self.writing = writing
        self.pipeline = pipeline

    def __call__(self, job: Job) -> JobResult:
        content_item_id = job.payload.get("content_item_id")
        if not isinstance(content_item_id, str) or not content_item_id.strip():
            return JobResult(success=False, message="WRITE_LINKEDIN_POST requires payload.content_item_id")
        post = self.writing.write(content_item_id=content_item_id.strip(), platform=Platform.LINKEDIN)
        if self.pipeline is not None:
            self.pipeline.record_artifact(
                content_item_id=content_item_id.strip(),
                artifact_type=ArtifactType.POST,
                artifact_id=post.id,
                job_id=job.id,
                metadata={"platform": post.platform.value, "version_number": post.version_number},
            )
        return JobResult(
            success=True,
            message=f"wrote LinkedIn post for content item {content_item_id}",
            metadata={
                "post_artifact_id": post.id,
                "content_item_id": post.content_item_id,
                "platform": post.platform.value,
                "version_number": post.version_number,
                "post_length": len(post.hook) + len(post.body) + len(post.call_to_action),
                "estimated_reading_time_seconds": post.estimated_reading_time_seconds,
            },
        )
