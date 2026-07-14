"""Finite state machine for ContentItem lifecycle stages."""

from __future__ import annotations

from content_engine.domain import ContentItemStage


class ContentLifecycleStateMachine:
    _allowed: dict[ContentItemStage, set[ContentItemStage]] = {
        ContentItemStage.DISCOVERED: {ContentItemStage.KNOWLEDGE_READY, ContentItemStage.ARCHIVED},
        ContentItemStage.KNOWLEDGE_READY: {ContentItemStage.PLANNED, ContentItemStage.ARCHIVED},
        ContentItemStage.PLANNED: {ContentItemStage.WRITING_READY, ContentItemStage.ARCHIVED},
        ContentItemStage.WRITING_READY: {ContentItemStage.IMAGE_READY, ContentItemStage.ARCHIVED},
        ContentItemStage.IMAGE_READY: {ContentItemStage.READY_TO_PUBLISH, ContentItemStage.ARCHIVED},
        ContentItemStage.READY_TO_PUBLISH: {ContentItemStage.PUBLISHED, ContentItemStage.ARCHIVED},
        ContentItemStage.PUBLISHED: {ContentItemStage.ARCHIVED},
        ContentItemStage.ARCHIVED: set(),
    }

    def can_transition(self, from_stage: ContentItemStage, to_stage: ContentItemStage) -> bool:
        return to_stage in self._allowed[from_stage]

    def require_transition(self, from_stage: ContentItemStage, to_stage: ContentItemStage) -> None:
        if not self.can_transition(from_stage, to_stage):
            raise ContentLifecycleError(f"Invalid lifecycle transition: {from_stage.value} -> {to_stage.value}")


class ContentLifecycleError(ValueError):
    """Raised when a lifecycle transition is invalid."""

