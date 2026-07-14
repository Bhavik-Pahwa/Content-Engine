"""Publishing value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from content_engine.domain import ImageArtifact, Platform, PostArtifact


@dataclass(frozen=True)
class PublishRequest:
    content_item_id: str
    platform: Platform
    post: PostArtifact
    image: ImageArtifact | None
    text: str
    dry_run: bool
    screenshot_dir: Path
    session_dir: Path
    timeout_seconds: float
    attempt_id: str
    linkedin_author_name: str | None = None
    linkedin_target_page_name: str | None = None
    headless: bool = True


@dataclass(frozen=True)
class PublishResult:
    published: bool
    status_url: str | None = None
    screenshot_before_path: Path | None = None
    screenshot_after_path: Path | None = None
    screenshot_error_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PublishingProviderError(RuntimeError):
    """Raised when a publisher fails."""


class AuthenticationRequiredError(PublishingProviderError):
    """Raised when the persistent browser session is not authenticated."""
