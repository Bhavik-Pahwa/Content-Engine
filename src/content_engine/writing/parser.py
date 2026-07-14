"""Parse provider output into structured post drafts."""

from __future__ import annotations

from typing import Any
import json
import re

from content_engine.writing.models import GeneratedPost


def parse_generated_post(text: str) -> GeneratedPost:
    payload = _extract_json(text)
    return GeneratedPost(
        title=str(payload.get("title", "")).strip(),
        hook=str(payload.get("hook", "")).strip(),
        body=str(payload.get("body", "")).strip(),
        call_to_action=str(payload.get("call_to_action", "")).strip(),
        hashtags=_hashtags(payload.get("hashtags", ())),
        generation_metadata={"raw_response_format": "json"},
    )


def _extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped.strip(), flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise PostParseError("Generated response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise PostParseError("Generated response must be a JSON object")
    return payload


def _hashtags(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split() if item.strip())
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


class PostParseError(ValueError):
    """Raised when generated post text cannot be parsed."""
