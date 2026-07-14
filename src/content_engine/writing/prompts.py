"""Prompt registry and rendering."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
import hashlib
import re

from content_engine.writing.models import RenderedPrompt


class PromptRegistry:
    def __init__(self, prompt_dir: Path) -> None:
        self.prompt_dir = prompt_dir

    def render(self, name: str, variables: dict[str, Any]) -> RenderedPrompt:
        path = self.prompt_dir / f"{name}.md"
        if not path.exists():
            raise PromptError(f"Prompt not found: {path}")
        text = path.read_text(encoding="utf-8")
        version = _extract_version(text)
        rendered = _SafeFormatDict(variables).render(text)
        return RenderedPrompt(name=name, version=version, text=rendered)


class PromptError(ValueError):
    """Raised when prompt loading or rendering fails."""


class _SafeFormatDict(defaultdict):
    def __init__(self, values: dict[str, Any]) -> None:
        super().__init__(str)
        self.values = {key: _stringify(value) for key, value in values.items()}

    def __missing__(self, key: str) -> str:
        raise PromptError(f"Missing prompt variable: {key}")

    def __getitem__(self, key: str) -> str:
        if key not in self.values:
            return self.__missing__(key)
        return self.values[key]

    def render(self, text: str) -> str:
        return text.format_map(self)


def _extract_version(text: str) -> str:
    match = re.search(r"<!--\s*version:\s*([^>]+?)\s*-->", text)
    if match:
        return match.group(1).strip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:12]


def _stringify(value: Any) -> str:
    if isinstance(value, (tuple, list)):
        return "\n".join(f"- {item}" for item in value)
    return str(value)
