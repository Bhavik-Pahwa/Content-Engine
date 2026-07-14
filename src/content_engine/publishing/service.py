"""Publishing service."""

from __future__ import annotations

import logging
import time

from content_engine.config import PublishingSettings, RuntimeSettings
from content_engine.db.repositories import RepositoryRegistry
from content_engine.domain import ArtifactType, ContentItem, ContentItemStage, Platform, PublicationArtifact
from content_engine.publishing.models import PublishRequest
from content_engine.publishing.providers import Publisher


class PublishingService:
    def __init__(
        self,
        *,
        repositories: RepositoryRegistry,
        publisher: Publisher,
        publishing_settings: PublishingSettings,
        runtime_settings: RuntimeSettings,
        logger: logging.Logger | None = None,
    ) -> None:
        self.repositories = repositories
        self.publisher = publisher
        self.publishing_settings = publishing_settings
        self.runtime_settings = runtime_settings
        self.logger = logger or logging.getLogger(__name__)

    def publish_next(self, *, platform: Platform = Platform.LINKEDIN) -> PublicationArtifact | None:
        content_item = self._next_ready_content_item()
        if content_item is None:
            return None
        return self.publish_content_item(content_item.id, platform=platform)

    def publish_content_item(self, content_item_id: str, *, platform: Platform = Platform.LINKEDIN) -> PublicationArtifact:
        existing = self.repositories.publications.published_for_content_item(content_item_id, platform)
        if existing is not None:
            self.logger.info(
                "publishing_already_completed",
                extra={"component": "publishing", "content_item_id": content_item_id, "publication_artifact_id": existing.id},
            )
            return existing
        content_item = self.repositories.content_items.required(content_item_id)
        if content_item.stage != ContentItemStage.READY_TO_PUBLISH:
            raise PublishingServiceError(
                f"Content item must be ready_to_publish before publishing: {content_item.id} is {content_item.stage.value}"
            )
        post = self.repositories.posts.latest_for_content_item(content_item_id, platform)
        if post is None:
            raise PublishingServiceError(f"Missing {platform.value} post artifact for content item: {content_item_id}")
        image = self.repositories.images.latest_for_content_item(content_item_id, platform)
        if image is None and self.publishing_settings.require_image:
            raise PublishingServiceError(f"Missing required image artifact for content item: {content_item_id}")
        attempt = self.repositories.publications.create_attempt(
            content_item_id=content_item_id,
            platform=platform,
            post_artifact_id=post.id,
            image_artifact_id=image.id if image is not None else None,
            playwright_session=str(self.publishing_settings.linkedin_session_dir),
            metadata={
                "provider": self.publisher.metadata.name,
                "dry_run": self.runtime_settings.dry_run,
                "simulate": self.publishing_settings.simulate,
                "linkedin_target_page_name": self.publishing_settings.linkedin_target_page_name,
                "headless": self.publishing_settings.headless,
            },
        )
        text = _post_text(post)
        started = time.monotonic()
        self.logger.info(
            "publisher_started",
            extra={
                "component": "publishing",
                "content_item_id": content_item_id,
                "attempt_id": attempt.id,
                "platform": platform.value,
                "dry_run": self.runtime_settings.dry_run,
            },
        )
        try:
            result = self.publisher.publish(
                PublishRequest(
                    content_item_id=content_item_id,
                    platform=platform,
                    post=post,
                    image=image,
                    text=text,
                    dry_run=self.runtime_settings.dry_run,
                    screenshot_dir=self.publishing_settings.screenshot_dir,
                    session_dir=self.publishing_settings.linkedin_session_dir,
                    timeout_seconds=self.publishing_settings.timeout_seconds,
                    attempt_id=attempt.id,
                    linkedin_author_name=self.publishing_settings.linkedin_author_name,
                    linkedin_target_page_name=self.publishing_settings.linkedin_target_page_name,
                    headless=self.publishing_settings.headless,
                )
            )
        except Exception as exc:
            duration = time.monotonic() - started
            failed = self.repositories.publications.mark_failed(
                attempt.id,
                error=str(exc) or exc.__class__.__name__,
                screenshot_before_path=None,
                screenshot_error_path=self.publishing_settings.screenshot_dir / f"{attempt.id}_error.png",
                duration_seconds=duration,
                metadata={"provider": self.publisher.metadata.name, "exception_type": exc.__class__.__name__},
            )
            self.logger.exception(
                "publisher_failed",
                extra={"component": "publishing", "content_item_id": content_item_id, "attempt_id": attempt.id},
            )
            raise PublishingServiceError(str(exc) or exc.__class__.__name__) from exc
        duration = time.monotonic() - started
        if not result.published:
            skipped = self.repositories.publications.mark_skipped(
                attempt.id,
                error="dry-run: not published" if self.runtime_settings.dry_run else None,
                screenshot_before_path=result.screenshot_before_path,
                screenshot_after_path=result.screenshot_after_path,
                duration_seconds=duration,
                metadata={**result.metadata, "provider": self.publisher.metadata.name},
            )
            self.logger.info(
                "publisher_dry_run_completed",
                extra={"component": "publishing", "content_item_id": content_item_id, "attempt_id": attempt.id},
            )
            return skipped
        published = self.repositories.publications.mark_published(
            attempt.id,
            url=result.status_url,
            screenshot_before_path=result.screenshot_before_path,
            screenshot_after_path=result.screenshot_after_path,
            duration_seconds=duration,
            metadata={**result.metadata, "provider": self.publisher.metadata.name},
        )
        if published.publish_timestamp is not None:
            self.repositories.intelligence.mark_metrics_published(
                content_item_id=content_item_id,
                platform=platform,
                post_artifact_id=post.id,
                image_artifact_id=image.id if image is not None else None,
                publishing_timestamp=published.publish_timestamp,
            )
        self.logger.info(
            "post_published",
            extra={
                "component": "publishing",
                "content_item_id": content_item_id,
                "publication_artifact_id": published.id,
                "duration_seconds": duration,
            },
        )
        return published

    def _next_ready_content_item(self) -> ContentItem | None:
        with self.repositories.content_items.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM content_items
                WHERE stage = ? AND status = ?
                ORDER BY updated_at ASC
                LIMIT 1
                """,
                (ContentItemStage.READY_TO_PUBLISH.value, "active"),
            ).fetchone()
        return self.repositories.content_items.required(str(row["id"])) if row else None


class PublishingServiceError(RuntimeError):
    """Raised when publishing cannot proceed."""


def _post_text(post) -> str:
    return "\n\n".join(
        part for part in (post.hook, post.body, post.call_to_action, " ".join(post.hashtags)) if part.strip()
    )
