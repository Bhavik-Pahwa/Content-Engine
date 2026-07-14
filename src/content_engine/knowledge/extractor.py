"""HTML article extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from typing import Any
import re

from content_engine.knowledge.models import ExtractedArticle, FetchResult


class ArticleExtractor:
    def __init__(self, *, min_clean_text_words: int) -> None:
        self.min_clean_text_words = min_clean_text_words

    def extract(self, fetch: FetchResult) -> ExtractedArticle:
        parser = _ArticleHTMLParser()
        parser.feed(fetch.html)
        title = parser.best_title()
        clean_text = parser.clean_text()
        if len(clean_text.split()) < self.min_clean_text_words:
            raise ArticleExtractionError("Extracted article text is too short")
        return ExtractedArticle(
            title=title or fetch.final_url,
            clean_text=clean_text,
            author=parser.author(),
            publication_date=parser.publication_date(),
            canonical_url=parser.canonical_url() or fetch.final_url,
            metadata={"extraction_strategy": "stdlib_html_parser"},
        )


class ArticleExtractionError(RuntimeError):
    """Raised when article extraction fails."""


class _ArticleHTMLParser(HTMLParser):
    _skip_tags = {"script", "style", "noscript", "svg", "canvas", "nav", "footer", "header", "form", "aside"}
    _block_tags = {"p", "li", "blockquote", "h1", "h2", "h3"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.current_tag: str | None = None
        self.current_parts: list[str] = []
        self.blocks: list[str] = []
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag in self._skip_tags:
            self.skip_depth += 1
            return
        if tag == "meta":
            key = attrs_dict.get("name") or attrs_dict.get("property")
            content = attrs_dict.get("content")
            if key and content:
                self.meta[key.lower()] = content.strip()
        if tag == "link":
            rel = attrs_dict.get("rel", "").lower()
            href = attrs_dict.get("href")
            if rel and href:
                self.links[rel] = href.strip()
        if self.skip_depth:
            return
        if tag in self._block_tags or tag == "title":
            self.current_tag = tag
            self.current_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._skip_tags and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if self.current_tag == tag:
            text = _clean_whitespace(" ".join(self.current_parts))
            if text:
                if tag == "title":
                    self.title_parts.append(text)
                elif tag == "h1":
                    self.h1_parts.append(text)
                    self.blocks.append(text)
                else:
                    self.blocks.append(text)
            self.current_tag = None
            self.current_parts = []

    def handle_data(self, data: str) -> None:
        if self.skip_depth or self.current_tag is None:
            return
        text = unescape(data).strip()
        if text:
            self.current_parts.append(text)

    def best_title(self) -> str:
        return (
            self.meta.get("og:title")
            or self.meta.get("twitter:title")
            or (self.h1_parts[0] if self.h1_parts else "")
            or (self.title_parts[0] if self.title_parts else "")
        )

    def clean_text(self) -> str:
        useful_blocks = [block for block in self.blocks if len(block.split()) >= 4]
        return "\n\n".join(dict.fromkeys(useful_blocks))

    def author(self) -> str | None:
        return self.meta.get("author") or self.meta.get("article:author") or self.meta.get("byl")

    def canonical_url(self) -> str | None:
        return self.links.get("canonical") or self.meta.get("og:url")

    def publication_date(self) -> datetime | None:
        raw = self.meta.get("article:published_time") or self.meta.get("date") or self.meta.get("publishdate")
        if not raw:
            return None
        return _parse_date(raw)


def _clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _parse_date(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

