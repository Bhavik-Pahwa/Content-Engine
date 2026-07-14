"""Draft quality validation."""

from __future__ import annotations

from dataclasses import dataclass
import re

from content_engine.config import WritingSettings
from content_engine.domain import Platform
from content_engine.writing.models import GeneratedPost


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    failures: tuple[str, ...] = ()


class PostValidator:
    def __init__(self, settings: WritingSettings, duplicate_texts: tuple[str, ...] = ()) -> None:
        self.settings = settings
        self.duplicate_texts = duplicate_texts

    def validate(self, post: GeneratedPost, *, platform: Platform) -> ValidationResult:
        failures: list[str] = []
        text = post.full_text
        length = len(text)
        if length < self.settings.min_post_characters:
            failures.append("post is below minimum length")
        if length > self.settings.max_post_characters:
            failures.append("post exceeds maximum length")
        if not post.hook.strip():
            failures.append("hook is missing")
        if not post.body.strip():
            failures.append("body is missing")
        if platform == Platform.LINKEDIN and len(post.hashtags) > self.settings.max_hashtags:
            failures.append("too many hashtags")
        for phrase in self.settings.banned_phrases:
            if phrase.lower() in text.lower():
                failures.append(f"banned phrase present: {phrase}")
        if _has_repeated_phrase(text):
            failures.append("repeated phrase detected")
        if _formatting_is_poor(text):
            failures.append("formatting quality is poor")
        if _near_duplicate(text, self.duplicate_texts):
            failures.append("duplicate or near-duplicate draft detected")
        return ValidationResult(ok=not failures, failures=tuple(failures))


def _has_repeated_phrase(text: str) -> bool:
    words = re.findall(r"[A-Za-z']+", text.lower())
    phrases = [" ".join(words[index : index + 4]) for index in range(max(0, len(words) - 3))]
    seen: set[str] = set()
    for phrase in phrases:
        if phrase in seen:
            return True
        seen.add(phrase)
    return False


def _formatting_is_poor(text: str) -> bool:
    if "\n\n\n\n" in text:
        return True
    lines = [line for line in text.splitlines() if line.strip()]
    return any(len(line) > 700 for line in lines)


def _near_duplicate(text: str, previous_texts: tuple[str, ...]) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False
    for previous in previous_texts:
        previous_normalized = _normalize(previous)
        if normalized == previous_normalized:
            return True
        shared = set(normalized.split()) & set(previous_normalized.split())
        total = set(normalized.split()) | set(previous_normalized.split())
        if total and len(shared) / len(total) >= 0.9:
            return True
    return False


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))
