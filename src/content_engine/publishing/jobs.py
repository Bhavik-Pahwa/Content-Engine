"""Job handlers for publishing."""

from __future__ import annotations

from typing import Any

from content_engine.domain import ArtifactType, Job, Platform, PublishingStatus
from content_engine.orchestration import JobResult
from content_engine.publishing.service import PublishingService


PUBLISH_LINKEDIN = "PUBLISH_LINKEDIN"


class PublishLinkedInJobHandler:
    def __init__(self, publishing: PublishingService, pipeline: Any | None = None) -> None:
        self.publishing = publishing
        self.pipeline = pipeline

    def __call__(self, job: Job) -> JobResult:
        content_item_id = job.payload.get("content_item_id")
        if not isinstance(content_item_id, str) or not content_item_id.strip():
            return JobResult(success=False, message="PUBLISH_LINKEDIN requires payload.content_item_id")
        artifact = self.publishing.publish_content_item(content_item_id.strip(), platform=Platform.LINKEDIN)
        if artifact.status == PublishingStatus.PUBLISHED and self.pipeline is not None:
            self.pipeline.record_artifact(
                content_item_id=content_item_id.strip(),
                artifact_type=ArtifactType.PUBLISHING,
                artifact_id=artifact.id,
                job_id=job.id,
                metadata={"platform": artifact.platform.value, "url": artifact.url},
            )
        return JobResult(
            success=True,
            message=f"published LinkedIn content item {content_item_id}",
            metadata={
                "publication_artifact_id": artifact.id,
                "content_item_id": artifact.content_item_id,
                "status": artifact.status.value,
                "url": artifact.url,
            },
        )
