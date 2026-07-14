"""Hacker News topic provider using the official Firebase API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import urlopen
import json
import time

from content_engine.discovery.models import TopicCandidate
from content_engine.providers import ProviderMetadata


class HackerNewsClient(Protocol):
    def top_story_ids(self, *, timeout_seconds: float) -> list[int]:
        """Return top story IDs."""

    def item(self, item_id: int, *, timeout_seconds: float) -> dict[str, Any] | None:
        """Return item metadata."""


class UrlLibHackerNewsClient:
    base_url = "https://hacker-news.firebaseio.com/v0"

    def top_story_ids(self, *, timeout_seconds: float) -> list[int]:
        data = self._get_json(f"{self.base_url}/topstories.json", timeout_seconds=timeout_seconds)
        if not isinstance(data, list):
            raise HackerNewsProviderError("topstories response was not a list")
        return [int(item_id) for item_id in data if isinstance(item_id, int)]

    def item(self, item_id: int, *, timeout_seconds: float) -> dict[str, Any] | None:
        data = self._get_json(f"{self.base_url}/item/{item_id}.json", timeout_seconds=timeout_seconds)
        if data is None:
            return None
        if not isinstance(data, dict):
            raise HackerNewsProviderError(f"item response was not an object: {item_id}")
        return data

    @staticmethod
    def _get_json(url: str, *, timeout_seconds: float) -> Any:
        try:
            with urlopen(url, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise HackerNewsProviderError(str(exc)) from exc


@dataclass(frozen=True)
class HackerNewsProvider:
    fetch_limit: int
    request_timeout_seconds: float
    retry_count: int
    client: HackerNewsClient
    metadata: ProviderMetadata = ProviderMetadata(
        name="hacker_news",
        provider_type="topic",
        version="0.1.0",
        requires_network=True,
        cost_profile="free",
        capabilities=("top_stories",),
    )

    def discover_topics(self) -> list[TopicCandidate]:
        story_ids = self._with_retries(lambda: self.client.top_story_ids(timeout_seconds=self.request_timeout_seconds))
        candidates: list[TopicCandidate] = []
        for story_id in story_ids[: self.fetch_limit]:
            item = self._with_retries(lambda story_id=story_id: self.client.item(story_id, timeout_seconds=self.request_timeout_seconds))
            candidate = self._candidate_from_item(item)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def _candidate_from_item(self, item: dict[str, Any] | None) -> TopicCandidate | None:
        if not item or item.get("deleted") or item.get("dead"):
            return None
        if item.get("type") != "story":
            return None
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        url = item.get("url")
        hn_id = item.get("id")
        if not isinstance(url, str) or not url.strip():
            url = f"https://news.ycombinator.com/item?id={hn_id}" if hn_id is not None else None
        return TopicCandidate(
            title=title.strip(),
            url=url,
            source="hacker_news",
            provider_name=self.metadata.name,
            description=None,
            author=item.get("by") if isinstance(item.get("by"), str) else None,
            score=item.get("score") if isinstance(item.get("score"), int) else None,
            published_at=_published_at(item.get("time")),
            metadata={
                "hacker_news_id": hn_id,
                "descendants": item.get("descendants"),
                "type": item.get("type"),
            },
        )

    def _with_retries(self, call):
        attempts = self.retry_count + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return call()
            except Exception as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(min(0.25 * (attempt + 1), 1.0))
        raise HackerNewsProviderError(str(last_error)) from last_error


class HackerNewsProviderError(RuntimeError):
    """Raised when Hacker News provider calls fail."""


def _published_at(raw: Any) -> datetime | None:
    if not isinstance(raw, int):
        return None
    return datetime.fromtimestamp(raw, tz=timezone.utc)
