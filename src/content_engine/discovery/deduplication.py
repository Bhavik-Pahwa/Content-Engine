"""Duplicate detection for discovered topics."""

from __future__ import annotations

from dataclasses import dataclass

from content_engine.db import TopicRepository
from content_engine.discovery.models import TopicCandidate
from content_engine.discovery.normalization import normalize_title, normalize_url, title_similarity


@dataclass(frozen=True)
class DuplicateDecision:
    duplicate: bool
    reason: str | None
    normalized_url: str | None
    normalized_title: str


class TopicDeduplicator:
    def __init__(self, topics: TopicRepository, *, title_similarity_threshold: float) -> None:
        self.topics = topics
        self.title_similarity_threshold = title_similarity_threshold

    def evaluate(self, candidate: TopicCandidate, seen_titles: set[str], seen_urls: set[str]) -> DuplicateDecision:
        normalized_url = normalize_url(candidate.url)
        normalized_title = normalize_title(candidate.title)
        if normalized_url and normalized_url in seen_urls:
            return DuplicateDecision(True, "duplicate URL in provider batch", normalized_url, normalized_title)
        if normalized_title in seen_titles:
            return DuplicateDecision(True, "duplicate title in provider batch", normalized_url, normalized_title)
        if self.topics.exists_by_normalized_url(normalized_url):
            return DuplicateDecision(True, "duplicate URL in database", normalized_url, normalized_title)
        if self.topics.exists_by_normalized_title(normalized_title):
            return DuplicateDecision(True, "duplicate title in database", normalized_url, normalized_title)
        for existing_title in self.topics.normalized_titles():
            if title_similarity(normalized_title, existing_title) >= self.title_similarity_threshold:
                return DuplicateDecision(True, "near-duplicate title in database", normalized_url, normalized_title)
        for existing_title in seen_titles:
            if title_similarity(normalized_title, existing_title) >= self.title_similarity_threshold:
                return DuplicateDecision(True, "near-duplicate title in provider batch", normalized_url, normalized_title)
        return DuplicateDecision(False, None, normalized_url, normalized_title)

