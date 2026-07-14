"""Job handlers for topic discovery."""

from __future__ import annotations

from content_engine.discovery.service import TopicDiscoveryService
from content_engine.domain import Job
from content_engine.orchestration import JobResult


DISCOVER_TOPICS = "DISCOVER_TOPICS"


class DiscoverTopicsJobHandler:
    def __init__(self, discovery: TopicDiscoveryService) -> None:
        self.discovery = discovery

    def __call__(self, _job: Job) -> JobResult:
        result = self.discovery.discover()
        return JobResult(
            success=True,
            message=f"discovered {len(result.topics)} topics",
            metadata=result.stats.as_metadata(),
        )
