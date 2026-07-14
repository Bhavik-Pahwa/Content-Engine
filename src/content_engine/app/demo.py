"""Manual end-to-end demo pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Callable, TypeVar

from content_engine.domain import (
    ArtifactType,
    ContentArtifact,
    ContentItem,
    ContentItemStage,
    ContentItemStatus,
    ContentPlan,
    KnowledgeDocument,
    ImageArtifact,
    Platform,
    PostArtifact,
    Topic,
    TopicStatus,
)
from content_engine.services import ServiceContainer


T = TypeVar("T")


@dataclass(frozen=True)
class DemoStageResult:
    name: str
    duration_seconds: float


@dataclass(frozen=True)
class DemoResult:
    topic: Topic
    knowledge_summary: str
    persona: str
    hook: str
    post: PostArtifact
    image: ImageArtifact
    duration_seconds: float
    stages: tuple[DemoStageResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PreparedDemoContent:
    topic: Topic
    content_item: ContentItem
    knowledge: KnowledgeDocument


class DemoPipeline:
    def __init__(self, container: ServiceContainer) -> None:
        self.container = container
        self.logger = container.logger
        self.stage_results: list[DemoStageResult] = []

    def run_once(self) -> DemoResult:
        started = monotonic()
        ranked_topics = self._run_stage("discover_topics", self._discover_ranked_topics)
        prepared = self._prepare_content_with_knowledge(ranked_topics)
        if prepared.content_item.stage == ContentItemStage.DISCOVERED:
            self._run_stage(
                "record_knowledge_artifact",
                lambda: self.container.pipeline.record_artifact(
                    content_item_id=prepared.content_item.id,
                    artifact_type=ArtifactType.KNOWLEDGE,
                    artifact_id=prepared.knowledge.id,
                    schedule_next=False,
                ),
            )
        plan = self._get_or_create_plan(prepared)
        post = self._get_or_create_post(prepared)
        image = self._get_or_create_image(prepared)
        self._run_stage(
            "record_content_intelligence",
            lambda: self.container.content_intelligence.record_for_content_item(
                prepared.content_item.id,
                notes="recorded by demo mode",
            ),
        )
        return DemoResult(
            topic=prepared.topic,
            knowledge_summary=prepared.knowledge.summary,
            persona=plan.writing_persona,
            hook=plan.hook_style,
            post=post,
            image=image,
            duration_seconds=monotonic() - started,
            stages=tuple(self.stage_results),
        )

    def _discover_ranked_topics(self) -> tuple[Topic, ...]:
        result = self.container.topic_discovery.discover()
        eligible_topics = [topic for topic in result.topics if topic.source_url and self._topic_is_available(topic)]
        if not eligible_topics:
            eligible_topics = [
                topic
                for topic in self.container.repositories.topics.list_all()
                if topic.source_url and topic.status != TopicStatus.SKIPPED and self._topic_is_available(topic)
            ]
            if eligible_topics:
                self.logger.info(
                    "demo_using_stored_topics",
                    extra={"component": "demo", "topic_count": len(eligible_topics)},
                )
        if not eligible_topics:
            raise DemoPipelineError("Discovery produced no new or stored topics with source URLs")
        return tuple(sorted(eligible_topics, key=_topic_rank_score, reverse=True))

    def _topic_is_available(self, topic: Topic) -> bool:
        content_item = self.container.repositories.content_items.find_by_topic(topic.id)
        if content_item is None:
            return True
        return content_item.status == ContentItemStatus.ACTIVE and content_item.stage not in {
            ContentItemStage.PUBLISHED,
            ContentItemStage.ARCHIVED,
        }

    def _prepare_content_with_knowledge(self, ranked_topics: tuple[Topic, ...]) -> PreparedDemoContent:
        failures: list[str] = []
        for topic in ranked_topics:
            content_item = self._run_stage(
                "create_content_item",
                lambda topic=topic: self.container.pipeline.create_content_item_for_topic(topic.id),
            )
            try:
                knowledge = self._get_or_build_knowledge(topic, content_item)
            except Exception as exc:
                failures.append(f"{topic.title}: {exc}")
                self.container.repositories.topics.set_status(topic.id, TopicStatus.SKIPPED)
                self.container.pipeline.mark_failed(
                    content_item.id,
                    reason=f"demo knowledge extraction failed: {exc}",
                )
                self.logger.warning(
                    "demo_topic_skipped",
                    extra={
                        "component": "demo",
                        "topic_id": topic.id,
                        "title": topic.title,
                        "reason": str(exc),
                    },
                )
                continue
            selected = self.container.repositories.topics.set_status(topic.id, TopicStatus.SELECTED)
            self._log_selected_topic(selected)
            return PreparedDemoContent(topic=selected, content_item=content_item, knowledge=knowledge)
        failure_text = "; ".join(failures[-3:]) if failures else "no eligible topics"
        raise DemoPipelineError(f"No discovered topics produced extractable article text. Last failures: {failure_text}")

    def _get_or_build_knowledge(self, topic: Topic, content_item: ContentItem) -> KnowledgeDocument:
        artifact = self._latest_artifact(content_item.id, ArtifactType.KNOWLEDGE)
        if artifact is not None and content_item.stage != ContentItemStage.DISCOVERED:
            return self.container.repositories.knowledge.required(artifact.artifact_id)
        return self._run_stage(
            "build_knowledge",
            lambda topic=topic: self.container.knowledge.build_for_topic(topic.id),
        )

    def _get_or_create_plan(self, prepared: PreparedDemoContent) -> ContentPlan:
        artifact = self._latest_artifact(prepared.content_item.id, ArtifactType.PLAN)
        current_item = self.container.repositories.content_items.required(prepared.content_item.id)
        if artifact is not None and current_item.stage in {
            ContentItemStage.PLANNED,
            ContentItemStage.WRITING_READY,
            ContentItemStage.IMAGE_READY,
            ContentItemStage.READY_TO_PUBLISH,
            ContentItemStage.PUBLISHED,
        }:
            return self.container.repositories.content_plans.required(artifact.artifact_id)
        plan = self._run_stage("plan_content", lambda: self.container.content_planning.plan_topic(prepared.topic.id))
        self._run_stage(
            "record_plan_artifact",
            lambda: self.container.pipeline.record_artifact(
                content_item_id=prepared.content_item.id,
                artifact_type=ArtifactType.PLAN,
                artifact_id=plan.id,
                schedule_next=False,
            ),
        )
        return plan

    def _get_or_create_post(self, prepared: PreparedDemoContent) -> PostArtifact:
        artifact = self._latest_artifact(prepared.content_item.id, ArtifactType.POST)
        current_item = self.container.repositories.content_items.required(prepared.content_item.id)
        if artifact is not None and current_item.stage in {
            ContentItemStage.WRITING_READY,
            ContentItemStage.IMAGE_READY,
            ContentItemStage.READY_TO_PUBLISH,
            ContentItemStage.PUBLISHED,
        }:
            return self.container.repositories.posts.required(artifact.artifact_id)
        post = self._run_stage(
            "write_linkedin_draft",
            lambda: self.container.writing.write(content_item_id=prepared.content_item.id, platform=Platform.LINKEDIN),
        )
        self._run_stage(
            "record_post_artifact",
            lambda: self.container.pipeline.record_artifact(
                content_item_id=prepared.content_item.id,
                artifact_type=ArtifactType.POST,
                artifact_id=post.id,
                metadata={"platform": post.platform.value, "version_number": post.version_number, "demo_mode": True},
                schedule_next=False,
            ),
        )
        return post

    def _get_or_create_image(self, prepared: PreparedDemoContent) -> ImageArtifact:
        artifact = self._latest_artifact(prepared.content_item.id, ArtifactType.IMAGE)
        current_item = self.container.repositories.content_items.required(prepared.content_item.id)
        if artifact is not None and current_item.stage in {
            ContentItemStage.IMAGE_READY,
            ContentItemStage.READY_TO_PUBLISH,
            ContentItemStage.PUBLISHED,
        }:
            return self.container.repositories.images.required_artifact(artifact.artifact_id)
        image = self._run_stage(
            "generate_linkedin_image",
            lambda: self.container.image_generation.generate_for_content_item(
                content_item_id=prepared.content_item.id,
                platform=Platform.LINKEDIN,
            ),
        )
        self._run_stage(
            "record_image_artifact",
            lambda: self.container.pipeline.record_artifact(
                content_item_id=prepared.content_item.id,
                artifact_type=ArtifactType.IMAGE,
                artifact_id=image.id,
                metadata={
                    "platform": image.platform.value,
                    "provider": image.provider,
                    "model": image.model,
                    "file_path": str(image.file_path),
                    "demo_mode": True,
                },
                schedule_next=False,
            ),
        )
        return image

    def _latest_artifact(self, content_item_id: str, artifact_type: ArtifactType) -> ContentArtifact | None:
        artifacts = [
            artifact
            for artifact in self.container.repositories.content_items.artifacts_for_item(content_item_id)
            if artifact.artifact_type == artifact_type
        ]
        return artifacts[-1] if artifacts else None

    def _log_selected_topic(self, topic: Topic) -> None:
        self.logger.info(
            "demo_topic_selected",
            extra={
                "component": "demo",
                "topic_id": topic.id,
                "title": topic.title,
                "source": topic.source,
                "score": topic.score,
                "rank_score": _topic_rank_score(topic),
            },
        )

    def _run_stage(self, name: str, action: Callable[[], T]) -> T:
        started = monotonic()
        self.logger.info("demo_stage_started", extra={"component": "demo", "stage": name})
        try:
            result = action()
        except Exception:
            duration = monotonic() - started
            self.logger.exception(
                "demo_stage_failed",
                extra={"component": "demo", "stage": name, "duration_seconds": duration},
            )
            raise
        duration = monotonic() - started
        self.stage_results.append(DemoStageResult(name=name, duration_seconds=duration))
        self.logger.info(
            "demo_stage_completed",
            extra={"component": "demo", "stage": name, "duration_seconds": duration},
        )
        return result


class DemoPipelineError(RuntimeError):
    """Raised when the demo pipeline cannot complete."""


def run_demo_pipeline(container: ServiceContainer) -> DemoResult:
    return DemoPipeline(container).run_once()


def print_demo_report(result: DemoResult) -> None:
    print("=" * 50)
    print("DEMO PIPELINE COMPLETE")
    print("=" * 50)
    print()
    print("Selected Topic")
    print(result.topic.title)
    print()
    print("Source")
    print(result.topic.source)
    print()
    print("Knowledge Summary")
    print(result.knowledge_summary)
    print()
    print("Chosen Persona")
    print(result.persona)
    print()
    print("Chosen Hook")
    print(result.hook)
    print()
    print("LinkedIn Draft")
    print(_post_text(result.post))
    print()
    print("LinkedIn Image")
    print(result.image.file_path)
    print()
    print("=" * 50)
    print("Artifacts Available")
    print("Topic OK")
    print("Knowledge OK")
    print("Plan OK")
    print("Draft OK")
    print("Image OK")
    print("=" * 50)
    print()
    print("Pipeline Duration")
    print(f"{result.duration_seconds:.2f} seconds")
    print("=" * 50)


def print_demo_failure(exc: Exception) -> None:
    print("=" * 50)
    print("DEMO PIPELINE FAILED")
    print("=" * 50)
    print()
    print(str(exc))
    print()
    print("Completed artifacts were preserved. Check logs for stage details.")
    print("=" * 50)


def _topic_rank_score(topic: Topic) -> float:
    score = float(topic.score or 0)
    metadata = topic.metadata or {}
    category_bonus = 25.0 if metadata.get("filter_category") else 0.0
    keyword_bonus = 10.0 if metadata.get("filter_keyword") else 0.0
    summary_bonus = min(len(topic.summary or "") / 20.0, 15.0)
    title_bonus = min(len(topic.title) / 10.0, 10.0)
    return score + category_bonus + keyword_bonus + summary_bonus + title_bonus


def _post_text(post: PostArtifact) -> str:
    parts = [post.hook, post.body, post.call_to_action, " ".join(post.hashtags)]
    return "\n\n".join(part for part in parts if part.strip())
