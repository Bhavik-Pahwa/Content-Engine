"""Writing engine models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_engine.domain import ContentItem, ContentPlan, KnowledgeDocument, Platform


@dataclass(frozen=True)
class RenderedPrompt:
    name: str
    version: str
    text: str


@dataclass(frozen=True)
class LLMRequest:
    system_prompt: str
    user_prompt: str
    platform: Platform
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider_name: str
    model: str | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GeneratedPost:
    title: str
    hook: str
    body: str
    call_to_action: str
    hashtags: tuple[str, ...]
    generation_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        parts = [self.hook, self.body, self.call_to_action, " ".join(self.hashtags)]
        return "\n\n".join(part for part in parts if part.strip())


@dataclass(frozen=True)
class WritingContext:
    content_item: ContentItem
    knowledge: KnowledgeDocument
    plan: ContentPlan
    platform: Platform
