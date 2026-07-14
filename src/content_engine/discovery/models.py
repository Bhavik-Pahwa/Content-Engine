"""Models used by the topic discovery subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from content_engine.domain import Topic


@dataclass(frozen=True)
class TopicCandidate:
    title: str
    url: str | None
    source: str
    provider_name: str
    description: str | None = None
    author: str | None = None
    score: int | None = None
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryStats:
    providers_called: int = 0
    stories_fetched: int = 0
    stories_accepted: int = 0
    stories_rejected: int = 0
    duplicate_count: int = 0
    database_insertions: int = 0
    failures: int = 0
    provider_response_time_seconds: dict[str, float] = field(default_factory=dict)

    def as_metadata(self) -> dict[str, Any]:
        return {
            "providers_called": self.providers_called,
            "stories_fetched": self.stories_fetched,
            "stories_accepted": self.stories_accepted,
            "stories_rejected": self.stories_rejected,
            "duplicate_count": self.duplicate_count,
            "database_insertions": self.database_insertions,
            "failures": self.failures,
            "provider_response_time_seconds": self.provider_response_time_seconds,
        }


@dataclass(frozen=True)
class DiscoveryResult:
    topics: tuple[Topic, ...]
    stats: DiscoveryStats

