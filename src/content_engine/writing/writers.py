"""Platform writer abstractions."""

from __future__ import annotations

from typing import Protocol
import time

from content_engine.config import WritingSettings
from content_engine.domain import Platform, PostArtifact
from content_engine.db.posts import PostArtifactRepository
from content_engine.writing.humanizer import PostHumanizer
from content_engine.writing.models import LLMRequest, WritingContext
from content_engine.writing.parser import parse_generated_post
from content_engine.writing.prompts import PromptRegistry
from content_engine.writing.providers import TextGenerationProvider
from content_engine.writing.validation import PostValidator


class Writer(Protocol):
    platform: Platform

    def write(self, context: WritingContext) -> PostArtifact:
        """Create a durable platform-specific draft."""


class LinkedInWriter:
    platform = Platform.LINKEDIN

    def __init__(
        self,
        *,
        provider: TextGenerationProvider,
        prompts: PromptRegistry,
        posts: PostArtifactRepository,
        settings: WritingSettings,
    ) -> None:
        self.provider = provider
        self.prompts = prompts
        self.posts = posts
        self.settings = settings
        self.humanizer = PostHumanizer(settings)

    def write(self, context: WritingContext) -> PostArtifact:
        variables = _prompt_variables(context)
        system_prompt = self.prompts.render("system", variables)
        validation_failures: tuple[str, ...] = ()
        last_response_metadata = {}
        for attempt in range(self.settings.generation_retry_limit + 1):
            started = time.monotonic()
            user_variables = {
                **variables,
                "validation_feedback": "\n".join(f"- {failure}" for failure in validation_failures),
            }
            user_prompt = self.prompts.render("linkedin", user_variables)
            response = self.provider.generate(
                LLMRequest(
                    system_prompt=system_prompt.text,
                    user_prompt=user_prompt.text,
                    platform=self.platform,
                    metadata={"attempt": attempt + 1},
                )
            )
            duration_seconds = time.monotonic() - started
            generated = parse_generated_post(response.text)
            humanized = self.humanizer.humanize(generated)
            validator = PostValidator(
                self.settings,
                duplicate_texts=tuple(
                    _post_text(post) for post in self.posts.list_for_content_item(context.content_item.id, self.platform)
                ),
            )
            validation = validator.validate(humanized, platform=self.platform)
            last_response_metadata = {
                "provider": response.provider_name,
                "model": response.model,
                "token_usage": response.token_usage,
                **response.metadata,
            }
            if validation.ok:
                return self.posts.create(
                    content_item_id=context.content_item.id,
                    platform=self.platform,
                    title=humanized.title,
                    hook=humanized.hook,
                    body=humanized.body,
                    call_to_action=humanized.call_to_action,
                    hashtags=humanized.hashtags,
                    estimated_reading_time_seconds=_estimated_reading_time_seconds(humanized.full_text),
                    generation_metadata={
                        **humanized.generation_metadata,
                        "attempts": attempt + 1,
                        "system_prompt": system_prompt.name,
                        "system_prompt_version": system_prompt.version,
                        "user_prompt": user_prompt.name,
                        "user_prompt_version": user_prompt.version,
                        "validation_failures": list(validation_failures),
                        "generation_duration_seconds": round(duration_seconds, 4),
                    },
                    provider_metadata=last_response_metadata,
                )
            validation_failures = validation.failures
        raise WritingValidationError(
            "Generated LinkedIn post failed validation after retries: " + "; ".join(validation_failures),
            provider_metadata=last_response_metadata,
            validation_failures=validation_failures,
        )


class WritingValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        provider_metadata: dict | None = None,
        validation_failures: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.provider_metadata = provider_metadata or {}
        self.validation_failures = validation_failures


def _prompt_variables(context: WritingContext) -> dict[str, object]:
    return {
        "content_item_title": context.content_item.title,
        "knowledge_title": context.knowledge.title,
        "knowledge_summary": context.knowledge.summary,
        "knowledge_keywords": context.knowledge.keywords,
        "technology_tags": context.knowledge.technology_tags,
        "companies": context.knowledge.companies,
        "concepts": context.knowledge.concepts,
        "primary_angle": context.plan.primary_angle,
        "target_audience": context.plan.target_audience,
        "content_goal": context.plan.content_goal,
        "content_type": context.plan.content_type,
        "hook_style": context.plan.hook_style,
        "writing_persona": context.plan.writing_persona,
        "key_points": context.plan.key_points,
        "call_to_action": context.plan.call_to_action,
        "visual_theme": context.plan.visual_theme,
    }


def _estimated_reading_time_seconds(text: str) -> int:
    words = max(1, len(text.split()))
    return max(15, round(words / 220 * 60))


def _post_text(post: PostArtifact) -> str:
    return "\n\n".join(
        part for part in (post.hook, post.body, post.call_to_action, " ".join(post.hashtags)) if part.strip()
    )
