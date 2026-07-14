"""Deterministic topic classification for content planning."""

from __future__ import annotations

from dataclasses import dataclass
import re

from content_engine.domain import Topic


@dataclass(frozen=True)
class TopicClassification:
    category: str
    difficulty_level: str
    keywords: tuple[str, ...]


class TopicClassifier:
    _categories: dict[str, tuple[str, ...]] = {
        "Artificial Intelligence": ("ai", "llm", "machine learning", "neural", "model", "agent"),
        "Developer Tools": ("tool", "cli", "compiler", "debugger", "ide", "terminal", "github"),
        "Software Engineering": ("architecture", "database", "distributed", "testing", "observability", "software"),
        "Cybersecurity": ("security", "vulnerability", "malware", "encryption", "supply chain"),
        "Cloud Infrastructure": ("cloud", "kubernetes", "aws", "azure", "gcp", "serverless", "docker"),
        "Web Development": ("web", "browser", "frontend", "backend", "css", "html", "react"),
        "Startups": ("startup", "founder", "venture", "product", "saas"),
        "Open Source": ("open source", "linux", "gnu", "license"),
    }

    _advanced_terms = ("distributed", "architecture", "internals", "compiler", "database", "kubernetes", "security")
    _intro_terms = ("intro", "beginner", "guide", "tutorial", "learn", "explained")

    def classify(self, topic: Topic) -> TopicClassification:
        text = f"{topic.title} {topic.summary or ''} {topic.source_url or ''}".lower()
        category = "Technology"
        best_score = 0
        for candidate, terms in self._categories.items():
            score = sum(1 for term in terms if term in text)
            if score > best_score:
                best_score = score
                category = candidate
        keywords = self.extract_keywords(topic)
        difficulty = self._difficulty(text)
        return TopicClassification(category=category, difficulty_level=difficulty, keywords=keywords)

    def extract_keywords(self, topic: Topic) -> tuple[str, ...]:
        text = f"{topic.title} {topic.summary or ''}".lower()
        words = [
            word
            for word in re.findall(r"[a-z][a-z0-9+#.-]{2,}", text)
            if word not in _STOP_WORDS
        ]
        result: list[str] = []
        for word in words:
            normalized = word.strip(".-")
            if normalized and normalized not in result:
                result.append(normalized)
            if len(result) == 6:
                break
        return tuple(result)

    def _difficulty(self, text: str) -> str:
        if any(term in text for term in self._advanced_terms):
            return "advanced"
        if any(term in text for term in self._intro_terms):
            return "introductory"
        return "intermediate"


_STOP_WORDS = {
    "about",
    "after",
    "and",
    "are",
    "for",
    "from",
    "how",
    "into",
    "new",
    "not",
    "that",
    "the",
    "this",
    "with",
    "why",
    "you",
    "your",
}

