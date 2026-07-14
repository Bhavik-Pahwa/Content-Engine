"""Writing service entry point."""

from __future__ import annotations

import logging

from content_engine.db.repositories import RepositoryRegistry
from content_engine.domain import ArtifactType, ContentItemStage, Platform, PostArtifact
from content_engine.writing.models import WritingContext
from content_engine.writing.writers import Writer


class WritingService:
    def __init__(
        self,
        *,
        repositories: RepositoryRegistry,
        writers: list[Writer],
        logger: logging.Logger | None = None,
    ) -> None:
        self.repositories = repositories
        self.writers = {writer.platform: writer for writer in writers}
        self.logger = logger or logging.getLogger(__name__)

    def write(self, *, content_item_id: str, platform: Platform) -> PostArtifact:
        writer = self.writers.get(platform)
        if writer is None:
            raise WritingServiceError(f"No writer registered for platform: {platform.value}")
        context = self._build_context(content_item_id=content_item_id, platform=platform)
        self.logger.info(
            "writing_started",
            extra={"content_item_id": content_item_id, "platform": platform.value, "stage": context.content_item.stage.value},
        )
        post = writer.write(context)
        self.logger.info(
            "writing_completed",
            extra={
                "content_item_id": content_item_id,
                "platform": platform.value,
                "post_artifact_id": post.id,
                "version_number": post.version_number,
            },
        )
        return post

    def _build_context(self, *, content_item_id: str, platform: Platform) -> WritingContext:
        content_item = self.repositories.content_items.required(content_item_id)
        if content_item.stage not in {ContentItemStage.PLANNED, ContentItemStage.WRITING_READY}:
            raise WritingServiceError(
                f"Content item must be planned or writing-ready before writing: {content_item.id} is {content_item.stage.value}"
            )
        knowledge_artifact = self._latest_artifact(content_item_id, ArtifactType.KNOWLEDGE)
        plan_artifact = self._latest_artifact(content_item_id, ArtifactType.PLAN)
        knowledge = self.repositories.knowledge.required(knowledge_artifact.artifact_id)
        plan = self.repositories.content_plans.required(plan_artifact.artifact_id)
        return WritingContext(content_item=content_item, knowledge=knowledge, plan=plan, platform=platform)

    def _latest_artifact(self, content_item_id: str, artifact_type: ArtifactType):
        artifacts = [
            artifact
            for artifact in self.repositories.content_items.artifacts_for_item(content_item_id)
            if artifact.artifact_type == artifact_type
        ]
        if not artifacts:
            raise WritingServiceError(f"Missing {artifact_type.value} artifact for content item: {content_item_id}")
        return artifacts[-1]


class WritingServiceError(RuntimeError):
    """Raised when writing cannot proceed."""
