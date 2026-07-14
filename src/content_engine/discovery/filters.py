"""Configurable topic filtering."""

from __future__ import annotations

from dataclasses import dataclass
import re

from content_engine.discovery.models import TopicCandidate


DEFAULT_ALLOWED_CATEGORIES: dict[str, tuple[str, ...]] = {
    "artificial_intelligence": (
        "ai",
        "artificial intelligence",
        "llm",
        "large language model",
        "machine learning",
        "deep learning",
        "neural network",
    ),
    "programming": ("programming", "python", "javascript", "typescript", "rust", "golang", "software"),
    "software_engineering": (
        "software engineering",
        "architecture",
        "distributed system",
        "database",
        "testing",
        "observability",
    ),
    "web_development": ("web", "frontend", "backend", "browser", "css", "html", "react", "node"),
    "cloud": ("cloud", "kubernetes", "aws", "azure", "gcp", "serverless", "docker"),
    "cybersecurity": ("security", "cybersecurity", "vulnerability", "malware", "encryption", "supply chain"),
    "developer_tools": ("developer tool", "dev tool", "compiler", "debugger", "cli", "ide", "terminal"),
    "open_source": ("open source", "github", "linux", "gnu"),
    "startups": ("startup", "founder", "venture", "product", "saas"),
}


@dataclass(frozen=True)
class FilterDecision:
    accepted: bool
    category: str | None
    keyword: str | None
    reason: str


class TopicFilter:
    def __init__(self, allowed_categories: dict[str, tuple[str, ...]] | None = None) -> None:
        self.allowed_categories = allowed_categories or DEFAULT_ALLOWED_CATEGORIES

    def evaluate(self, candidate: TopicCandidate) -> FilterDecision:
        haystack = " ".join(
            part for part in (candidate.title, candidate.description or "", candidate.url or "") if part
        ).lower()
        for category, keywords in self.allowed_categories.items():
            for keyword in keywords:
                if _keyword_matches(haystack, keyword):
                    return FilterDecision(True, category, keyword, "matched keyword")
        return FilterDecision(False, None, None, "no allowed category matched")


def _keyword_matches(haystack: str, keyword: str) -> bool:
    normalized = keyword.lower().strip()
    if not normalized:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])"
    return re.search(pattern, haystack) is not None
