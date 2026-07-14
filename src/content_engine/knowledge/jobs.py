"""Job handlers for the Knowledge Engine."""

from __future__ import annotations

from typing import Any

from content_engine.domain import ArtifactType
from content_engine.domain import Job
from content_engine.knowledge.service import KnowledgeService
from content_engine.orchestration import JobResult


BUILD_KNOWLEDGE = "BUILD_KNOWLEDGE"


class BuildKnowledgeJobHandler:
    def __init__(self, knowledge: KnowledgeService, pipeline: Any | None = None) -> None:
        self.knowledge = knowledge
        self.pipeline = pipeline

    def __call__(self, job: Job) -> JobResult:
        topic_id = job.payload.get("topic_id")
        if not isinstance(topic_id, str) or not topic_id.strip():
            return JobResult(success=False, message="BUILD_KNOWLEDGE requires payload.topic_id")
        document = self.knowledge.build_for_topic(topic_id.strip())
        content_item_id = job.payload.get("content_item_id")
        if self.pipeline is not None and isinstance(content_item_id, str) and content_item_id.strip():
            self.pipeline.record_artifact(
                content_item_id=content_item_id.strip(),
                artifact_type=ArtifactType.KNOWLEDGE,
                artifact_id=document.id,
                job_id=job.id,
            )
        return JobResult(
            success=True,
            message=f"built knowledge for topic {topic_id}",
            metadata={
                "knowledge_document_id": document.id,
                "topic_id": document.topic_id,
                "version_number": document.version_number,
                "word_count": document.word_count,
                "keyword_count": len(document.keywords),
                "technology_category": document.technology_category,
            },
        )
