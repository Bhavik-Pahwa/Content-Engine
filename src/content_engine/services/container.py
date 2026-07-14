"""Dependency container for shared services."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from content_engine.config import Settings
from content_engine.content_lifecycle.pipeline import PipelineCoordinator
from content_engine.db import Database, MigrationRunner, RepositoryRegistry
from content_engine.discovery import DEFAULT_ALLOWED_CATEGORIES, TopicDiscoveryService, TopicFilter
from content_engine.discovery.deduplication import TopicDeduplicator
from content_engine.discovery.jobs import DISCOVER_TOPICS, DiscoverTopicsJobHandler
from content_engine.discovery.providers import HackerNewsProvider, UrlLibHackerNewsClient
from content_engine.images import (
    GENERATE_IMAGE,
    GenerateImageJobHandler,
    ImageGenerationService,
    ImagePromptBuilder,
    ImageValidator,
    LocalDiffusersImageProvider,
    LocalTemplateImageProvider,
    StableDiffusionWebUIImageProvider,
)
from content_engine.intelligence import ContentIntelligenceService
from content_engine.knowledge import BUILD_KNOWLEDGE, BuildKnowledgeJobHandler, KnowledgeService
from content_engine.knowledge.extractor import ArticleExtractor
from content_engine.knowledge.fetcher import UrlLibContentFetcher
from content_engine.knowledge.processor import KnowledgeProcessor
from content_engine.orchestration import JobExecutionEngine, JobHandlerRegistry, RetryPolicy, RuntimeMetrics, Scheduler
from content_engine.planning import PLAN_CONTENT, ContentPlanningService, PlanContentJobHandler, TopicClassifier
from content_engine.providers import ProviderRegistry
from content_engine.publishing import (
    LinkedInPublisher,
    MockPublisher,
    PUBLISH_LINKEDIN,
    PublishLinkedInJobHandler,
    PublishingService,
)
from content_engine.storage import StoragePaths
from content_engine.workers import WorkerRegistry
from content_engine.writing import WRITE_LINKEDIN_POST, WriteLinkedInPostJobHandler, WritingService
from content_engine.writing.prompts import PromptRegistry
from content_engine.writing.providers import OpenRouterProvider
from content_engine.writing.writers import LinkedInWriter


@dataclass(frozen=True)
class ServiceContainer:
    settings: Settings
    logger: logging.Logger
    storage_paths: StoragePaths
    database: Database
    migrations: MigrationRunner
    repositories: RepositoryRegistry
    providers: ProviderRegistry
    workers: WorkerRegistry
    job_handlers: JobHandlerRegistry
    job_metrics: RuntimeMetrics
    job_engine: JobExecutionEngine
    scheduler: Scheduler
    topic_discovery: TopicDiscoveryService
    content_planning: ContentPlanningService
    knowledge: KnowledgeService
    pipeline: PipelineCoordinator
    writing: WritingService
    image_generation: ImageGenerationService
    content_intelligence: ContentIntelligenceService
    publishing: PublishingService


def build_service_container(
    *,
    settings: Settings,
    logger: logging.Logger,
    storage_paths: StoragePaths,
    database: Database,
    migrations: MigrationRunner,
) -> ServiceContainer:
    repositories = RepositoryRegistry.create(database)
    handlers = JobHandlerRegistry()
    metrics = RuntimeMetrics()
    retry_policy = RetryPolicy.from_settings(settings.runtime)
    topic_discovery = _build_topic_discovery(settings=settings, repositories=repositories, logger=logger)
    content_planning = _build_content_planning(settings=settings, repositories=repositories, logger=logger)
    knowledge = _build_knowledge(settings=settings, repositories=repositories, logger=logger)
    llm_provider = OpenRouterProvider(
        api_key=settings.writing.openrouter_api_key,
        model=settings.writing.openrouter_model,
        timeout_seconds=settings.writing.openrouter_timeout_seconds,
    )
    writing = _build_writing(
        settings=settings,
        repositories=repositories,
        provider=llm_provider,
        logger=logger,
    )
    image_provider = _build_image_provider(settings)
    image_generation = _build_image_generation(
        settings=settings,
        repositories=repositories,
        provider=image_provider,
        storage_paths=storage_paths,
        logger=logger,
    )
    content_intelligence = ContentIntelligenceService(repositories=repositories, settings=settings, logger=logger)
    publisher = MockPublisher() if settings.runtime.dry_run or settings.publishing.simulate else LinkedInPublisher()
    publishing = PublishingService(
        repositories=repositories,
        publisher=publisher,
        publishing_settings=settings.publishing,
        runtime_settings=settings.runtime,
        logger=logger,
    )
    pipeline = PipelineCoordinator(repositories=repositories, logger=logger)
    job_engine = JobExecutionEngine(
        jobs=repositories.jobs,
        handlers=handlers,
        retry_policy=retry_policy,
        metrics=metrics,
        logger=logger,
    )
    scheduler = Scheduler(
        jobs=repositories.jobs,
        engine=job_engine,
        metrics=metrics,
        settings=settings.runtime,
        logger=logger,
    )
    handlers.register(DISCOVER_TOPICS, DiscoverTopicsJobHandler(topic_discovery))
    handlers.register(BUILD_KNOWLEDGE, BuildKnowledgeJobHandler(knowledge, pipeline=pipeline))
    handlers.register(PLAN_CONTENT, PlanContentJobHandler(content_planning, pipeline=pipeline))
    handlers.register(WRITE_LINKEDIN_POST, WriteLinkedInPostJobHandler(writing, pipeline=pipeline))
    handlers.register(
        GENERATE_IMAGE,
        GenerateImageJobHandler(image_generation, pipeline=pipeline, intelligence=content_intelligence),
    )
    handlers.register(PUBLISH_LINKEDIN, PublishLinkedInJobHandler(publishing, pipeline=pipeline))
    provider_registry = ProviderRegistry(
        topic_providers=list(topic_discovery.providers),
        llm_providers=[llm_provider],
        image_providers=[image_provider],
        publisher_providers=[publisher],
    )
    return ServiceContainer(
        settings=settings,
        logger=logger,
        storage_paths=storage_paths,
        database=database,
        migrations=migrations,
        repositories=repositories,
        providers=provider_registry,
        workers=WorkerRegistry(),
        job_handlers=handlers,
        job_metrics=metrics,
        job_engine=job_engine,
        scheduler=scheduler,
        topic_discovery=topic_discovery,
        content_planning=content_planning,
        knowledge=knowledge,
        pipeline=pipeline,
        writing=writing,
        image_generation=image_generation,
        content_intelligence=content_intelligence,
        publishing=publishing,
    )


def _build_topic_discovery(
    *,
    settings: Settings,
    repositories: RepositoryRegistry,
    logger: logging.Logger,
) -> TopicDiscoveryService:
    providers = []
    enabled = {provider.strip().lower() for provider in settings.discovery.enabled_topic_providers}
    if "hacker_news" in enabled:
        providers.append(
            HackerNewsProvider(
                fetch_limit=settings.discovery.hacker_news_fetch_limit,
                request_timeout_seconds=settings.discovery.hacker_news_request_timeout_seconds,
                retry_count=settings.discovery.hacker_news_retry_count,
                client=UrlLibHackerNewsClient(),
            )
        )
    categories = settings.discovery.allowed_categories or DEFAULT_ALLOWED_CATEGORIES
    return TopicDiscoveryService(
        providers=providers,
        topic_filter=TopicFilter(categories),
        deduplicator=TopicDeduplicator(
            repositories.topics,
            title_similarity_threshold=settings.discovery.duplicate_title_similarity_threshold,
        ),
        topics=repositories.topics,
        logger=logger,
    )


def _build_content_planning(
    *,
    settings: Settings,
    repositories: RepositoryRegistry,
    logger: logging.Logger,
) -> ContentPlanningService:
    return ContentPlanningService(
        topics=repositories.topics,
        plans=repositories.content_plans,
        settings=settings.planning,
        classifier=TopicClassifier(),
        logger=logger,
    )


def _build_knowledge(
    *,
    settings: Settings,
    repositories: RepositoryRegistry,
    logger: logging.Logger,
) -> KnowledgeService:
    return KnowledgeService(
        topics=repositories.topics,
        knowledge=repositories.knowledge,
        fetcher=UrlLibContentFetcher(settings.knowledge),
        extractor=ArticleExtractor(min_clean_text_words=settings.knowledge.min_clean_text_words),
        processor=KnowledgeProcessor(),
        settings=settings.knowledge,
        logger=logger,
    )


def _build_writing(
    *,
    settings: Settings,
    repositories: RepositoryRegistry,
    provider: OpenRouterProvider,
    logger: logging.Logger,
) -> WritingService:
    prompt_registry = PromptRegistry(settings.writing.prompt_dir)
    writers = [
        LinkedInWriter(
            provider=provider,
            prompts=prompt_registry,
            posts=repositories.posts,
            settings=settings.writing,
        )
    ]
    return WritingService(repositories=repositories, writers=writers, logger=logger)


def _build_image_generation(
    *,
    settings: Settings,
    repositories: RepositoryRegistry,
    provider,
    storage_paths: StoragePaths,
    logger: logging.Logger,
) -> ImageGenerationService:
    return ImageGenerationService(
        repositories=repositories,
        provider=provider,
        prompt_builder=ImagePromptBuilder(settings.image),
        validator=ImageValidator(),
        settings=settings.image,
        images_dir=storage_paths.images,
        logger=logger,
    )


def _build_image_provider(settings: Settings):
    provider_name = settings.image.provider.strip().lower()
    template_provider = LocalTemplateImageProvider(model="local-template-v2")
    if provider_name in {"stable_diffusion_webui", "stable_diffusion", "sd_webui", "sd"}:
        return StableDiffusionWebUIImageProvider(
            settings=settings.image,
            fallback_provider=template_provider if settings.image.stable_diffusion_fallback_to_template else None,
        )
    if provider_name in {"local_diffusers", "diffusers"}:
        return LocalDiffusersImageProvider(settings=settings.image)
    return LocalTemplateImageProvider(model=settings.image.model)
