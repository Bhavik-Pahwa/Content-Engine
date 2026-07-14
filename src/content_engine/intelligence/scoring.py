"""Deterministic content quality scoring."""

from __future__ import annotations

from dataclasses import dataclass
import re

from content_engine.domain import PostArtifact


@dataclass(frozen=True)
class ScoreBreakdown:
    score: float
    reading_level: float
    length_score: float
    hook_quality: float
    paragraph_count: int
    hashtag_count: int
    duplicate_score: float
    prompt_confidence: float
    metadata: dict[str, object]


class ContentScorer:
    def score_post(self, post: PostArtifact, *, previous_posts: tuple[PostArtifact, ...] = ()) -> ScoreBreakdown:
        text = _post_text(post)
        words = re.findall(r"[A-Za-z0-9']+", text)
        sentences = max(1, len(re.findall(r"[.!?]+", text)))
        average_sentence_length = len(words) / sentences
        reading_level = min(100.0, max(0.0, 100.0 - abs(average_sentence_length - 18.0) * 3.5))
        character_count = len(text)
        length_score = _range_score(character_count, ideal_min=650, ideal_max=1400, hard_min=350, hard_max=1900)
        hook_quality = _hook_quality(post.hook)
        paragraph_count = len([part for part in post.body.split("\n\n") if part.strip()]) or 1
        hashtag_count = len(post.hashtags)
        duplicate_score = _duplicate_score(text, previous_posts)
        prompt_confidence = _prompt_confidence(post)
        score = round(
            reading_level * 0.18
            + length_score * 0.22
            + hook_quality * 0.22
            + duplicate_score * 0.18
            + prompt_confidence * 0.20,
            2,
        )
        return ScoreBreakdown(
            score=score,
            reading_level=round(reading_level, 2),
            length_score=round(length_score, 2),
            hook_quality=round(hook_quality, 2),
            paragraph_count=paragraph_count,
            hashtag_count=hashtag_count,
            duplicate_score=round(duplicate_score, 2),
            prompt_confidence=round(prompt_confidence, 2),
            metadata={
                "character_count": character_count,
                "word_count": len(words),
                "sentence_count": sentences,
                "average_sentence_length": round(average_sentence_length, 2),
            },
        )


def _range_score(value: int, *, ideal_min: int, ideal_max: int, hard_min: int, hard_max: int) -> float:
    if ideal_min <= value <= ideal_max:
        return 100.0
    if value < ideal_min:
        return max(0.0, 100.0 * (value - hard_min) / max(1, ideal_min - hard_min))
    return max(0.0, 100.0 * (hard_max - value) / max(1, hard_max - ideal_max))


def _hook_quality(hook: str) -> float:
    stripped = hook.strip()
    if not stripped:
        return 0.0
    score = 45.0
    if 80 <= len(stripped) <= 260:
        score += 25.0
    if "?" in stripped:
        score += 10.0
    if any(word in stripped.lower() for word in ("not", "why", "how", "best", "mistake", "useful")):
        score += 12.0
    if len(stripped.split()) <= 35:
        score += 8.0
    return min(100.0, score)


def _duplicate_score(text: str, previous_posts: tuple[PostArtifact, ...]) -> float:
    normalized = _normalize(text)
    if not previous_posts:
        return 100.0
    similarities = [_jaccard(normalized, _normalize(_post_text(post))) for post in previous_posts]
    return max(0.0, 100.0 * (1.0 - max(similarities, default=0.0)))


def _prompt_confidence(post: PostArtifact) -> float:
    metadata = post.generation_metadata
    required = ("system_prompt_version", "user_prompt_version", "attempts", "generation_duration_seconds")
    present = sum(1 for key in required if key in metadata)
    if post.provider_metadata.get("provider") and post.provider_metadata.get("model"):
        present += 1
    return present / 5 * 100.0


def _normalize(text: str) -> set[str]:
    return {word.lower() for word in re.findall(r"[A-Za-z0-9']+", text) if len(word) > 2}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _post_text(post: PostArtifact) -> str:
    return "\n\n".join(
        part for part in (post.hook, post.body, post.call_to_action, " ".join(post.hashtags)) if part.strip()
    )
