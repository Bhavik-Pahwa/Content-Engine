"""Provider framework contracts.

Concrete providers are intentionally not implemented in Sprint 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence

from content_engine.domain import PublishingRecord, Topic


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    provider_type: str
    version: str = "0.1.0"
    requires_network: bool = False
    cost_profile: str = "free"
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    ok: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


class TopicProvider(Protocol):
    metadata: ProviderMetadata

    def discover_topics(self) -> Sequence[Topic]:
        """Return candidate topics."""


class LLMProvider(Protocol):
    metadata: ProviderMetadata

    def generate(self, request: Any) -> Any:
        """Generate text from a structured provider request."""


class ImageProvider(Protocol):
    metadata: ProviderMetadata

    def generate(self, request: Any) -> Any:
        """Generate or compose an image asset from a structured request."""


class PublisherProvider(Protocol):
    metadata: ProviderMetadata

    def publish(self, record: PublishingRecord) -> PublishingRecord:
        """Publish a prepared record."""


@dataclass
class ProviderRegistry:
    topic_providers: list[TopicProvider] = field(default_factory=list)
    llm_providers: list[LLMProvider] = field(default_factory=list)
    image_providers: list[ImageProvider] = field(default_factory=list)
    publisher_providers: list[PublisherProvider] = field(default_factory=list)

    def health(self) -> list[HealthCheckResult]:
        results: list[HealthCheckResult] = []
        for provider in self._all_providers():
            results.append(
                HealthCheckResult(
                    name=provider.metadata.name,
                    ok=True,
                    message="registered",
                    details={
                        "provider_type": provider.metadata.provider_type,
                        "requires_network": provider.metadata.requires_network,
                    },
                )
            )
        return results

    def _all_providers(self) -> list[Any]:
        return [
            *self.topic_providers,
            *self.llm_providers,
            *self.image_providers,
            *self.publisher_providers,
        ]
