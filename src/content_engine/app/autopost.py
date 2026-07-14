"""Continuous autonomous posting loop."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import signal
import time

from content_engine.app.demo import DemoPipeline, DemoPipelineError, DemoResult, _post_text, _topic_rank_score
from content_engine.domain import ArtifactType, ContentItemStage, ContentItemStatus, Platform, Topic, TopicStatus
from content_engine.services import ServiceContainer


TECH_PATTERN = re.compile(
    r"\b("
    r"ai|llm|machine learning|deep learning|neural|model|agent|inference|training|"
    r"python|javascript|typescript|rust|golang|software|code|coding|programming|"
    r"developer|devtools?|cli|terminal|compiler|debugger|github|open source|linux|kernel|"
    r"security|vulnerability|exploit|malware|encryption|cloud|kubernetes|docker|"
    r"database|postgres|sqlite|react|browser|frontend|backend|api|server|gpu|"
    r"architecture|distributed|observability|testing|web|xai|gpt|claude|openrouter|glm|chromium"
    r")\b",
    re.IGNORECASE,
)
BLOCK_PATTERN = re.compile(
    r"\b(interrail|berkshire|vinyl record|overheated market|travel|railway|recipe|sports)\b",
    re.IGNORECASE,
)
LIMIT_ERROR_PATTERN = re.compile(
    r"(http error 402|payment required|http error 429|rate.?limit|quota|insufficient credits|credit balance|"
    r"authentication required|login required|checkpoint)",
    re.IGNORECASE,
)
BAD_PHRASES = ("agic box", "as an ai language model", "game changer", "unlock the power")


@dataclass(frozen=True)
class AutopostIterationResult:
    content_item_id: str
    publication_id: str
    topic_title: str
    image_provider: str
    image_model: str
    image_path: str
    pipeline_seconds: float
    image_seconds: float


@dataclass(frozen=True)
class AutopostRunResult:
    published: int
    attempts: int
    stopped_reason: str


class StrictAutopostPipeline(DemoPipeline):
    """Demo pipeline variant that avoids stale/off-brand topics."""

    def _discover_ranked_topics(self) -> tuple[Topic, ...]:
        result = self.container.topic_discovery.discover()
        eligible_topics = [
            topic
            for topic in result.topics
            if topic.source_url and self._topic_is_available(topic) and _is_strict_technical_topic(topic)
        ]
        if not eligible_topics:
            eligible_topics = [
                topic
                for topic in self.container.repositories.topics.list_all()
                if topic.source_url
                and topic.status != TopicStatus.SKIPPED
                and self._topic_is_available(topic)
                and _is_strict_technical_topic(topic)
            ]
            if eligible_topics:
                self.logger.info(
                    "autopost_using_stored_topics",
                    extra={"component": "autopost", "topic_count": len(eligible_topics)},
                )
        if not eligible_topics:
            raise DemoPipelineError("No strict technical topics available")
        return tuple(sorted(eligible_topics, key=_topic_rank_score, reverse=True))


class AutopostRunner:
    def __init__(
        self,
        container: ServiceContainer,
        *,
        delay_seconds: float,
        max_posts: int | None = None,
        max_consecutive_failures: int = 5,
    ) -> None:
        self.container = container
        self.delay_seconds = delay_seconds
        self.max_posts = max_posts
        self.max_consecutive_failures = max_consecutive_failures
        self.stop_requested = False

    def run_forever(self) -> AutopostRunResult:
        published = 0
        attempts = 0
        consecutive_failures = 0
        previous_sigint = signal.signal(signal.SIGINT, self._request_stop)
        previous_sigterm = signal.signal(signal.SIGTERM, self._request_stop)
        try:
            while not self.stop_requested and (self.max_posts is None or published < self.max_posts):
                attempts += 1
                print("=" * 72, flush=True)
                print(f"AUTOPOST ATTEMPT {attempts}", flush=True)
                try:
                    result = self.run_once()
                except Exception as exc:
                    consecutive_failures += 1
                    self.container.logger.exception(
                        "autopost_iteration_failed",
                        extra={"component": "autopost", "attempt": attempts, "consecutive_failures": consecutive_failures},
                    )
                    print(f"FAILED attempt {attempts}: {exc}", flush=True)
                    if is_limit_error(exc):
                        return AutopostRunResult(published, attempts, f"stopped on API/auth limit: {exc}")
                    if consecutive_failures >= self.max_consecutive_failures:
                        return AutopostRunResult(
                            published,
                            attempts,
                            f"stopped after {consecutive_failures} consecutive failures",
                        )
                    time.sleep(min(30.0, max(2.0, self.delay_seconds / 6)))
                    continue
                consecutive_failures = 0
                published += 1
                _print_iteration_result(result=result, published=published, max_posts=self.max_posts)
                if self.stop_requested or (self.max_posts is not None and published >= self.max_posts):
                    break
                time.sleep(self.delay_seconds)
        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)
        reason = "operator stop requested" if self.stop_requested else "max posts reached"
        return AutopostRunResult(published, attempts, reason)

    def run_once(self) -> AutopostIterationResult:
        _mark_known_bad_topics(self.container)
        result = StrictAutopostPipeline(self.container).run_once()
        _quality_check(result)
        content_item = self.container.repositories.content_items.find_by_topic(result.topic.id)
        if content_item is None:
            raise AutopostError("Pipeline did not create a content item")
        _ready_for_publish(self.container, content_item.id)
        publication = self.container.publishing.publish_content_item(content_item.id, platform=Platform.LINKEDIN)
        self.container.pipeline.record_artifact(
            content_item_id=content_item.id,
            artifact_type=ArtifactType.PUBLISHING,
            artifact_id=publication.id,
            metadata={"platform": "linkedin", "autopost": True},
            schedule_next=False,
        )
        return AutopostIterationResult(
            content_item_id=content_item.id,
            publication_id=publication.id,
            topic_title=result.topic.title,
            image_provider=result.image.provider,
            image_model=result.image.model,
            image_path=str(result.image.file_path),
            pipeline_seconds=result.duration_seconds,
            image_seconds=result.image.generation_time_seconds,
        )

    def _request_stop(self, signum: int, _frame: object) -> None:
        self.stop_requested = True
        self.container.logger.info("autopost_shutdown_requested", extra={"component": "autopost", "signal": signum})


class AutopostError(RuntimeError):
    """Raised when an autopost iteration cannot proceed."""


def is_limit_error(exc: Exception) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if LIMIT_ERROR_PATTERN.search(str(current)):
            return True
        current = current.__cause__ if isinstance(current.__cause__, BaseException) else None
    return False


def default_delay_seconds() -> float:
    raw = os.getenv("CONTENT_ENGINE_AUTOPOST_DELAY_SECONDS", "900")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 900.0


def default_max_consecutive_failures() -> int:
    raw = os.getenv("CONTENT_ENGINE_AUTOPOST_MAX_CONSECUTIVE_FAILURES", "5")
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def _quality_check(result: DemoResult) -> None:
    text = _post_text(result.post)
    lowered = text.lower()
    if len(text) < 400:
        raise AutopostError(f"Post too short ({len(text)} chars)")
    if len(result.post.hashtags) > 5:
        raise AutopostError(f"Too many hashtags ({len(result.post.hashtags)})")
    for phrase in BAD_PHRASES:
        if phrase in lowered:
            raise AutopostError(f"Blocked phrase found: {phrase}")
    if not _is_strict_technical_topic(result.topic):
        raise AutopostError(f"Topic failed strict technical gate: {result.topic.title}")


def _ready_for_publish(container: ServiceContainer, content_item_id: str) -> None:
    item = container.repositories.content_items.required(content_item_id)
    if item.stage == ContentItemStage.IMAGE_READY:
        container.repositories.content_items.transition(
            content_item_id,
            ContentItemStage.READY_TO_PUBLISH,
            reason="autopost ready for publication",
        )
    elif item.stage != ContentItemStage.READY_TO_PUBLISH:
        raise AutopostError(f"Content item is not publish-ready: {content_item_id} is {item.stage.value}")


def _mark_known_bad_topics(container: ServiceContainer) -> None:
    for topic in container.repositories.topics.list_all():
        if not _is_blocked_topic(topic):
            continue
        container.repositories.topics.set_status(topic.id, TopicStatus.SKIPPED)
        item = container.repositories.content_items.find_by_topic(topic.id)
        if item and item.status == ContentItemStatus.ACTIVE and item.stage != ContentItemStage.PUBLISHED:
            container.pipeline.mark_failed(item.id, reason="autopost skipped off-brand topic")


def _is_strict_technical_topic(topic: Topic) -> bool:
    text = _topic_text(topic)
    return not BLOCK_PATTERN.search(text) and TECH_PATTERN.search(text) is not None


def _is_blocked_topic(topic: Topic) -> bool:
    return BLOCK_PATTERN.search(_topic_text(topic)) is not None


def _topic_text(topic: Topic) -> str:
    return " ".join(part for part in (topic.title, topic.summary or "", topic.source_url or "") if part)


def _print_iteration_result(*, result: AutopostIterationResult, published: int, max_posts: int | None) -> None:
    target = "unbounded" if max_posts is None else str(max_posts)
    print(f"PUBLISHED {published}/{target}: {result.topic_title}", flush=True)
    print(f"Content item: {result.content_item_id}", flush=True)
    print(f"Publication: {result.publication_id}", flush=True)
    print(f"Image provider: {result.image_provider}", flush=True)
    print(f"Image model: {result.image_model}", flush=True)
    print(f"Image file: {result.image_path}", flush=True)
    print(f"Image seconds: {result.image_seconds:.2f}", flush=True)
    print(f"Pipeline seconds: {result.pipeline_seconds:.2f}", flush=True)
