"""Core domain models.

The foundation uses dataclasses rather than ORM models so domain concepts stay
independent of SQLite and future provider payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


class Platform(StrEnum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    X = "x"
    THREADS = "threads"
    BLOG = "blog"


class TopicStatus(StrEnum):
    DISCOVERED = "discovered"
    SELECTED = "selected"
    SKIPPED = "skipped"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class PublishingStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    SKIPPED = "skipped"


class PostArtifactStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class ImageArtifactStatus(StrEnum):
    CREATED = "created"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class ContentPlanStatus(StrEnum):
    PLANNED = "planned"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class KnowledgeDocumentStatus(StrEnum):
    CREATED = "created"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class ContentItemStage(StrEnum):
    DISCOVERED = "discovered"
    KNOWLEDGE_READY = "knowledge_ready"
    PLANNED = "planned"
    WRITING_READY = "writing_ready"
    IMAGE_READY = "image_ready"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentItemStatus(StrEnum):
    ACTIVE = "active"
    FAILED = "failed"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ArtifactType(StrEnum):
    TOPIC = "topic"
    KNOWLEDGE = "knowledge"
    PLAN = "plan"
    POST = "post"
    IMAGE = "image"
    PUBLISHING = "publishing"
    VIDEO = "video"
    ANALYTICS = "analytics"


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    source: str
    summary: str | None = None
    source_url: str | None = None
    author: str | None = None
    score: int | None = None
    provider_name: str | None = None
    status: TopicStatus = TopicStatus.DISCOVERED
    metadata: dict[str, Any] = field(default_factory=dict)
    published_at: datetime | None = None
    discovered_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ContentItem:
    id: str
    title: str
    stage: ContentItemStage
    status: ContentItemStatus
    source_topic_id: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ContentArtifact:
    id: str
    content_item_id: str
    artifact_type: ArtifactType
    artifact_id: str
    role: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ContentStageTransition:
    id: str
    content_item_id: str
    from_stage: ContentItemStage | None
    to_stage: ContentItemStage
    reason: str | None
    job_id: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ContentPlan:
    id: str
    topic_id: str
    version_number: int
    primary_angle: str
    target_audience: str
    content_goal: str
    content_type: str
    hook_style: str
    writing_persona: str
    visual_theme: str
    image_prompt: str
    video_prompt: str | None
    key_points: tuple[str, ...]
    call_to_action: str
    platform_targets: tuple[str, ...]
    status: ContentPlanStatus = ContentPlanStatus.PLANNED
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class KnowledgeDocument:
    id: str
    topic_id: str
    version_number: int
    title: str
    summary: str
    clean_text: str
    keywords: tuple[str, ...]
    named_entities: tuple[str, ...]
    technology_tags: tuple[str, ...]
    companies: tuple[str, ...]
    people: tuple[str, ...]
    concepts: tuple[str, ...]
    source_url: str
    canonical_url: str | None
    author: str | None
    publication_date: datetime | None
    word_count: int
    language: str
    reading_time_minutes: int
    reading_difficulty: str
    estimated_audience: str
    technology_category: str
    status: KnowledgeDocumentStatus = KnowledgeDocumentStatus.CREATED
    raw_html: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ContentAsset:
    id: str
    asset_type: str
    path: Path
    post_id: str | None = None
    provider_name: str | None = None
    status: str = "created"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Job:
    id: str
    job_type: str
    status: JobStatus = JobStatus.PENDING
    priority: int = 100
    payload: dict[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    attempts: int = 0
    max_attempts: int = 3
    run_after: datetime | None = None
    locked_by: str | None = None
    locked_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PublishingRecord:
    id: str
    post_id: str
    platform: Platform
    status: PublishingStatus = PublishingStatus.PENDING
    scheduled_for: datetime | None = None
    external_id: str | None = None
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublicationArtifact:
    id: str
    content_item_id: str
    platform: Platform
    post_artifact_id: str
    image_artifact_id: str | None
    status: PublishingStatus
    publish_timestamp: datetime | None = None
    playwright_session: str | None = None
    url: str | None = None
    retry_count: int = 0
    error: str | None = None
    screenshot_before_path: Path | None = None
    screenshot_after_path: Path | None = None
    screenshot_error_path: Path | None = None
    duration_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class PostArtifact:
    id: str
    content_item_id: str
    platform: Platform
    version_number: int
    title: str
    hook: str
    body: str
    call_to_action: str
    hashtags: tuple[str, ...]
    estimated_reading_time_seconds: int
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    status: PostArtifactStatus = PostArtifactStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ImagePrompt:
    id: str
    content_item_id: str
    platform: Platform
    positive_prompt: str
    negative_prompt: str | None
    style_metadata: dict[str, Any] = field(default_factory=dict)
    prompt_version: str = "1.0.0"
    prompt_hash: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ImageArtifact:
    id: str
    content_item_id: str
    prompt_id: str
    platform: Platform
    version_number: int
    provider: str
    model: str
    positive_prompt: str
    negative_prompt: str | None
    seed: int
    width: int
    height: int
    generation_time_seconds: float
    file_path: Path
    file_hash: str
    status: ImageArtifactStatus = ImageArtifactStatus.CREATED
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Experiment:
    id: str
    content_item_id: str
    prompt_version: str | None
    llm_provider: str | None
    llm_model: str | None
    temperature: float | None
    top_p: float | None
    image_provider: str | None
    image_model: str | None
    persona: str | None
    hook: str | None
    visual_theme: str | None
    generation_timestamp: datetime
    configuration_snapshot: dict[str, Any] = field(default_factory=dict)
    git_commit_hash: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ArtifactLineage:
    id: str
    content_item_id: str
    parent_artifact_type: ArtifactType
    parent_artifact_id: str
    child_artifact_type: ArtifactType
    child_artifact_id: str
    relationship: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ContentMetrics:
    id: str
    content_item_id: str
    platform: Platform
    post_artifact_id: str | None
    image_artifact_id: str | None
    publishing_timestamp: datetime | None = None
    collection_timestamp: datetime | None = None
    impressions: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    bookmarks: int | None = None
    click_through_rate: float | None = None
    engagement_rate: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ContentScore:
    id: str
    content_item_id: str
    artifact_type: ArtifactType
    artifact_id: str
    score: float
    reading_level: float
    length_score: float
    hook_quality: float
    paragraph_count: int
    hashtag_count: int
    duplicate_score: float
    prompt_confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
