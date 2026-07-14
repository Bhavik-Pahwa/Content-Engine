"""Deterministic knowledge processing."""

from __future__ import annotations

from collections import Counter
import math
import re

from content_engine.knowledge.models import ExtractedArticle, KnowledgeProcessingResult


class KnowledgeProcessor:
    def process(self, article: ExtractedArticle) -> KnowledgeProcessingResult:
        words = _words(article.clean_text)
        word_count = len(words)
        keywords = _keywords(words)
        technology_tags = _technology_tags(article.clean_text)
        companies = _companies(article.clean_text)
        people = _people(article.clean_text)
        concepts = _concepts(article.clean_text, keywords, technology_tags)
        named_entities = tuple(dict.fromkeys((*companies, *people, *concepts)))
        category = _technology_category(technology_tags, keywords)
        return KnowledgeProcessingResult(
            summary=_summary(article.clean_text),
            keywords=keywords,
            named_entities=named_entities[:20],
            technology_tags=technology_tags,
            companies=companies,
            people=people,
            concepts=concepts,
            word_count=word_count,
            language="en",
            reading_time_minutes=max(1, math.ceil(word_count / 220)),
            reading_difficulty=_reading_difficulty(words),
            estimated_audience=_estimated_audience(category, words),
            technology_category=category,
        )


def _summary(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    selected = [sentence.strip() for sentence in sentences if len(sentence.split()) >= 6][:2]
    summary = " ".join(selected) if selected else text[:280]
    return summary[:420].strip()


def _words(text: str) -> list[str]:
    return [word.lower() for word in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", text)]


def _keywords(words: list[str]) -> tuple[str, ...]:
    counter = Counter(word.strip(".-") for word in words if word not in _STOP_WORDS and len(word) > 2)
    return tuple(word for word, _count in counter.most_common(12))


def _technology_tags(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, patterns in _TECH_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            tags.append(tag)
    return tuple(tags)


def _companies(text: str) -> tuple[str, ...]:
    found = [company for company in _KNOWN_COMPANIES if re.search(rf"\b{re.escape(company)}\b", text, re.IGNORECASE)]
    return tuple(dict.fromkeys(found))


def _people(text: str) -> tuple[str, ...]:
    candidates = re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text)
    return tuple(name for name in dict.fromkeys(candidates) if name not in _KNOWN_COMPANIES)[:10]


def _concepts(text: str, keywords: tuple[str, ...], technology_tags: tuple[str, ...]) -> tuple[str, ...]:
    concepts = [tag for tag in technology_tags]
    concepts.extend(keyword.replace("-", " ") for keyword in keywords[:6])
    return tuple(dict.fromkeys(concepts))[:12]


def _technology_category(tags: tuple[str, ...], keywords: tuple[str, ...]) -> str:
    if "Artificial Intelligence" in tags:
        return "Artificial Intelligence"
    if "Cybersecurity" in tags:
        return "Cybersecurity"
    if "Cloud Infrastructure" in tags:
        return "Cloud Infrastructure"
    if "Developer Tools" in tags:
        return "Developer Tools"
    if "Web Development" in tags:
        return "Web Development"
    if "Open Source" in tags:
        return "Open Source"
    if any(keyword in {"startup", "founder", "product"} for keyword in keywords):
        return "Startups"
    return "Software Engineering"


def _reading_difficulty(words: list[str]) -> str:
    if not words:
        return "unknown"
    long_ratio = sum(1 for word in words if len(word) >= 10) / len(words)
    if long_ratio > 0.22:
        return "advanced"
    if long_ratio < 0.10:
        return "accessible"
    return "intermediate"


def _estimated_audience(category: str, words: list[str]) -> str:
    if category == "Artificial Intelligence":
        return "AI-aware builders and technical leaders"
    if category == "Cybersecurity":
        return "security-minded engineers and operators"
    if category == "Cloud Infrastructure":
        return "platform engineers and infrastructure leaders"
    if category == "Developer Tools":
        return "software developers and engineering teams"
    if len(words) > 1800:
        return "deep technical readers"
    return "technology practitioners"


_TECH_PATTERNS = {
    "Artificial Intelligence": (" artificial intelligence", " ai ", "llm", "machine learning", "neural", "model"),
    "Cybersecurity": ("security", "vulnerability", "malware", "encryption", "breach"),
    "Cloud Infrastructure": ("cloud", "kubernetes", "aws", "azure", "gcp", "serverless", "docker"),
    "Developer Tools": ("compiler", "debugger", "terminal", "cli", "ide", "developer tool"),
    "Web Development": ("browser", "frontend", "backend", "javascript", "typescript", "react", "css"),
    "Open Source": ("open source", "github", "linux", "gnu"),
}

_KNOWN_COMPANIES = (
    "OpenAI",
    "Google",
    "Microsoft",
    "Apple",
    "Amazon",
    "Meta",
    "Nvidia",
    "GitHub",
    "Cloudflare",
    "Vercel",
    "Docker",
    "Red Hat",
)

_STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "because",
    "been",
    "but",
    "can",
    "for",
    "from",
    "has",
    "have",
    "how",
    "into",
    "its",
    "not",
    "one",
    "that",
    "the",
    "their",
    "there",
    "this",
    "was",
    "were",
    "with",
    "you",
    "your",
}

