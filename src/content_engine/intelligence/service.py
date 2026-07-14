"""Content intelligence service."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
import logging
import subprocess
from typing import Any

from content_engine.config import Settings
from content_engine.db.repositories import RepositoryRegistry
from content_engine.domain import ArtifactType, ContentArtifact, ContentScore, Experiment, Platform
from content_engine.intelligence.scoring import ContentScorer


@dataclass(frozen=True)
class IntelligenceRecord:
    experiment: Experiment
    score: ContentScore
    lineage_count: int


class ContentIntelligenceService:
    def __init__(
        self,
        *,
        repositories: RepositoryRegistry,
        settings: Settings,
        scorer: ContentScorer | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.repositories = repositories
        self.settings = settings
        self.scorer = scorer or ContentScorer()
        self.logger = logger or logging.getLogger(__name__)

    def record_for_content_item(self, content_item_id: str, *, notes: str | None = None) -> IntelligenceRecord:
        content_item = self.repositories.content_items.required(content_item_id)
        artifacts = self.repositories.content_items.artifacts_for_item(content_item_id)
        topic_artifact = _latest_artifact(artifacts, ArtifactType.TOPIC)
        knowledge_artifact = _latest_artifact(artifacts, ArtifactType.KNOWLEDGE)
        plan_artifact = _latest_artifact(artifacts, ArtifactType.PLAN)
        post_artifact = _latest_artifact(artifacts, ArtifactType.POST)
        image_artifact_link = _latest_artifact(artifacts, ArtifactType.IMAGE)
        if post_artifact is None:
            raise ContentIntelligenceError(f"Missing post artifact for content item: {content_item_id}")
        if knowledge_artifact is None or plan_artifact is None:
            raise ContentIntelligenceError(f"Missing knowledge or plan artifact for content item: {content_item_id}")

        knowledge = self.repositories.knowledge.required(knowledge_artifact.artifact_id)
        plan = self.repositories.content_plans.required(plan_artifact.artifact_id)
        post = self.repositories.posts.required(post_artifact.artifact_id)
        image = (
            self.repositories.images.required_artifact(image_artifact_link.artifact_id)
            if image_artifact_link is not None
            else None
        )
        prompt = self.repositories.images.required_prompt(image.prompt_id) if image is not None else None
        existing_experiment = self.repositories.intelligence.experiment_for_artifacts(
            content_item_id=content_item_id,
            post_artifact_id=post.id,
            image_artifact_id=image.id if image is not None else None,
        )

        lineage_count = self._record_lineage(
            content_item_id=content_item_id,
            topic_artifact=topic_artifact,
            knowledge_artifact=knowledge_artifact,
            plan_artifact=plan_artifact,
            post_artifact=post_artifact,
            image_artifact=image_artifact_link,
        )
        previous_posts = tuple(
            existing for existing in self.repositories.posts.list_for_content_item(content_item_id, post.platform) if existing.id != post.id
        )
        score_data = self.scorer.score_post(post, previous_posts=previous_posts)
        score = self.repositories.intelligence.create_score(
            content_item_id=content_item_id,
            artifact_type=ArtifactType.POST,
            artifact_id=post.id,
            score=score_data.score,
            reading_level=score_data.reading_level,
            length_score=score_data.length_score,
            hook_quality=score_data.hook_quality,
            paragraph_count=score_data.paragraph_count,
            hashtag_count=score_data.hashtag_count,
            duplicate_score=score_data.duplicate_score,
            prompt_confidence=score_data.prompt_confidence,
            metadata=score_data.metadata,
        )
        self.repositories.intelligence.create_metrics_placeholder(
            content_item_id=content_item_id,
            platform=post.platform,
            post_artifact_id=post.id,
            image_artifact_id=image.id if image is not None else None,
            metadata={"status": "placeholder", "source": "content_intelligence"},
        )
        experiment = self.repositories.intelligence.create_experiment(
            content_item_id=content_item_id,
            knowledge_document_id=knowledge.id,
            content_plan_id=plan.id,
            post_artifact_id=post.id,
            image_artifact_id=image.id if image is not None else None,
            prompt_version=post.generation_metadata.get("user_prompt_version"),
            system_prompt_version=post.generation_metadata.get("system_prompt_version"),
            user_prompt_version=post.generation_metadata.get("user_prompt_version"),
            image_prompt_version=prompt.prompt_version if prompt is not None else None,
            llm_provider=post.provider_metadata.get("provider"),
            llm_model=post.provider_metadata.get("model"),
            temperature=_optional_float(post.provider_metadata.get("temperature")),
            top_p=_optional_float(post.provider_metadata.get("top_p")),
            image_provider=image.provider if image is not None else None,
            image_model=image.model if image is not None else None,
            persona=plan.writing_persona,
            hook=plan.hook_style,
            visual_theme=plan.visual_theme,
            generation_timestamp=post.created_at,
            configuration_snapshot=self._configuration_snapshot(),
            git_commit_hash=_git_commit_hash(),
            notes=notes,
            metadata={
                "content_item_title": content_item.title,
                "knowledge_version": knowledge.version_number,
                "plan_version": plan.version_number,
                "post_version": post.version_number,
                "image_version": image.version_number if image is not None else None,
                "image_prompt_id": prompt.id if prompt is not None else None,
                "image_prompt_hash": prompt.prompt_hash if prompt is not None else None,
                "writing_attempts": post.generation_metadata.get("attempts"),
                "writing_duration_seconds": post.generation_metadata.get("generation_duration_seconds"),
                "image_generation_duration_seconds": image.generation_time_seconds if image is not None else None,
                "content_score": score.score,
            },
        ) if existing_experiment is None else existing_experiment
        self.logger.info(
            "content_intelligence_recorded",
            extra={
                "component": "intelligence",
                "content_item_id": content_item_id,
                "experiment_id": experiment.id,
                "score": score.score,
            },
        )
        return IntelligenceRecord(experiment=experiment, score=score, lineage_count=lineage_count)

    def _record_lineage(
        self,
        *,
        content_item_id: str,
        topic_artifact: ContentArtifact | None,
        knowledge_artifact: ContentArtifact | None,
        plan_artifact: ContentArtifact | None,
        post_artifact: ContentArtifact | None,
        image_artifact: ContentArtifact | None,
    ) -> int:
        edges = [
            (topic_artifact, knowledge_artifact, "topic_to_knowledge"),
            (knowledge_artifact, plan_artifact, "knowledge_to_plan"),
            (plan_artifact, post_artifact, "plan_to_post"),
            (post_artifact, image_artifact, "post_to_image"),
        ]
        count = 0
        for parent, child, relationship in edges:
            if parent is None or child is None:
                continue
            self.repositories.intelligence.add_lineage(
                content_item_id=content_item_id,
                parent_artifact_type=parent.artifact_type,
                parent_artifact_id=parent.artifact_id,
                child_artifact_type=child.artifact_type,
                child_artifact_id=child.artifact_id,
                relationship=relationship,
            )
            count += 1
        return count

    def _configuration_snapshot(self) -> dict[str, Any]:
        snapshot = asdict(self.settings) if is_dataclass(self.settings) else _object_dict(self.settings)
        writing = snapshot.get("writing", {})
        if isinstance(writing, dict):
            writing["openrouter_api_key"] = "<redacted>" if writing.get("openrouter_api_key") else None
        return _jsonable(snapshot)


class ContentIntelligenceError(RuntimeError):
    """Raised when content intelligence cannot be recorded."""


def _latest_artifact(artifacts: list[ContentArtifact], artifact_type: ArtifactType) -> ContentArtifact | None:
    matches = [artifact for artifact in artifacts if artifact.artifact_type == artifact_type]
    return matches[-1] if matches else None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    value = result.stdout.strip()
    return value or None


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _object_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {key: _object_dict(item) if hasattr(item, "__dict__") else item for key, item in vars(value).items()}
