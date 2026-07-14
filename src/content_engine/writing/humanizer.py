"""Deterministic post-processing for generated drafts."""

from __future__ import annotations

import re

from content_engine.config import WritingSettings
from content_engine.writing.models import GeneratedPost


class PostHumanizer:
    def __init__(self, settings: WritingSettings) -> None:
        self.settings = settings

    def humanize(self, post: GeneratedPost) -> GeneratedPost:
        body = _normalize_spacing(post.body)
        body = _remove_banned_phrases(body, self.settings.banned_phrases)
        body = _vary_paragraphs(body)
        if not self.settings.allow_emojis:
            body = _remove_emojis(body)
        hashtags = _normalize_hashtags(post.hashtags, self.settings.max_hashtags)
        return GeneratedPost(
            title=_normalize_spacing(post.title),
            hook=_normalize_spacing(_remove_banned_phrases(post.hook, self.settings.banned_phrases)),
            body=body,
            call_to_action=_normalize_spacing(post.call_to_action),
            hashtags=hashtags,
            generation_metadata={**post.generation_metadata, "humanized": True},
        )


def _normalize_spacing(text: str) -> str:
    lines = [" ".join(line.strip().split()) for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)


def _remove_banned_phrases(text: str, phrases: tuple[str, ...]) -> str:
    result = text
    for phrase in phrases:
        result = re.sub(re.escape(phrase), "", result, flags=re.IGNORECASE)
    return _normalize_spacing(result)


def _vary_paragraphs(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    paragraphs: list[str] = []
    current: list[str] = []
    for index, sentence in enumerate(sentence for sentence in sentences if sentence):
        current.append(sentence)
        if len(current) >= 2 or (index + 1) % 3 == 0:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs) if paragraphs else text


def _normalize_hashtags(hashtags: tuple[str, ...], max_hashtags: int) -> tuple[str, ...]:
    normalized: list[str] = []
    for hashtag in hashtags:
        value = hashtag.strip()
        if not value:
            continue
        if not value.startswith("#"):
            value = f"#{value}"
        value = re.sub(r"[^#A-Za-z0-9_]", "", value)
        if len(value) > 1 and value.lower() not in {item.lower() for item in normalized}:
            normalized.append(value)
        if len(normalized) >= max_hashtags:
            break
    return tuple(normalized)


def _remove_emojis(text: str) -> str:
    return "".join(character for character in text if ord(character) < 10_000)
