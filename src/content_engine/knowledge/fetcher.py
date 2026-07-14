"""Article fetching."""

from __future__ import annotations

from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import time

from content_engine.config import KnowledgeSettings
from content_engine.knowledge.models import FetchResult


class ContentFetcher(Protocol):
    def fetch(self, url: str) -> FetchResult:
        """Fetch a URL and return HTML content."""


class UrlLibContentFetcher:
    def __init__(self, settings: KnowledgeSettings) -> None:
        self.settings = settings

    def fetch(self, url: str) -> FetchResult:
        last_error: Exception | None = None
        for attempt in range(self.settings.retry_count + 1):
            try:
                return self._fetch_once(url)
            except KnowledgeFetchError as exc:
                last_error = exc
                if attempt < self.settings.retry_count:
                    time.sleep(min(0.5 * (attempt + 1), 2.0))
        raise KnowledgeFetchError(str(last_error)) from last_error

    def _fetch_once(self, url: str) -> FetchResult:
        request = Request(url, headers={"User-Agent": self.settings.user_agent, "Accept": "text/html,application/xhtml+xml"})
        try:
            with urlopen(request, timeout=self.settings.request_timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                if not _is_html(content_type):
                    raise KnowledgeFetchError(f"Unsupported content type: {content_type}")
                raw = response.read(self.settings.max_download_bytes + 1)
                if len(raw) > self.settings.max_download_bytes:
                    raise KnowledgeFetchError("Response exceeded maximum download size")
                charset = response.headers.get_content_charset() or "utf-8"
                html = raw.decode(charset, errors="replace")
                return FetchResult(
                    url=url,
                    final_url=response.geturl(),
                    content_type=content_type,
                    html=html,
                    status_code=getattr(response, "status", None),
                )
        except HTTPError as exc:
            raise KnowledgeFetchError(f"HTTP error {exc.code}") from exc
        except (OSError, URLError, UnicodeError) as exc:
            raise KnowledgeFetchError(str(exc)) from exc


class KnowledgeFetchError(RuntimeError):
    """Raised when content cannot be fetched."""


def _is_html(content_type: str) -> bool:
    normalized = content_type.lower()
    return "text/html" in normalized or "application/xhtml" in normalized

