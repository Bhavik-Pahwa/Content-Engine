"""Content planning service."""

from __future__ import annotations

import logging

from content_engine.config import PlanningSettings
from content_engine.db import ContentPlanRepository, TopicRepository
from content_engine.domain import ContentPlan, Topic
from content_engine.planning.classifier import TopicClassifier
from content_engine.planning.selection import choose_persona, choose_rotating


class ContentPlanningService:
    def __init__(
        self,
        *,
        topics: TopicRepository,
        plans: ContentPlanRepository,
        settings: PlanningSettings,
        classifier: TopicClassifier,
        logger: logging.Logger,
    ) -> None:
        self.topics = topics
        self.plans = plans
        self.settings = settings
        self.classifier = classifier
        self.logger = logger

    def plan_topic(self, topic_id: str) -> ContentPlan:
        self.logger.info("planner_started", extra={"component": "planning", "topic_id": topic_id})
        topic = self.topics.get(topic_id)
        if topic is None:
            self.logger.error("planner_failed", extra={"component": "planning", "topic_id": topic_id, "error": "topic not found"})
            raise ContentPlanningError(f"Topic not found: {topic_id}")
        self.logger.info("planner_topic_selected", extra={"component": "planning", "topic_id": topic.id, "title": topic.title})
        classification = self.classifier.classify(topic)
        prior_plan_count = len(self.plans.list_for_topic(topic.id))
        seed = f"{topic.id}:{topic.title}:{classification.category}"
        persona = choose_persona(
            self.settings.enabled_personas,
            category=classification.category,
            difficulty_level=classification.difficulty_level,
            seed=seed,
            offset=prior_plan_count,
        )
        hook_style = choose_rotating(self.settings.hook_styles, seed=seed, offset=prior_plan_count)
        visual_theme = self._visual_theme(classification.category, seed=seed, offset=prior_plan_count)
        self.logger.info(
            "planner_choices_selected",
            extra={
                "component": "planning",
                "topic_id": topic.id,
                "persona": persona,
                "hook_style": hook_style,
                "visual_theme": visual_theme,
                "category": classification.category,
            },
        )
        plan = self.plans.create(
            topic_id=topic.id,
            primary_angle=self._primary_angle(topic, classification.category),
            target_audience=self._target_audience(classification.category, classification.difficulty_level),
            content_goal=self._content_goal(hook_style),
            content_type=self._content_type(hook_style),
            hook_style=hook_style,
            writing_persona=persona,
            visual_theme=visual_theme,
            image_prompt=self._image_prompt(topic, classification.category, visual_theme),
            video_prompt=None,
            key_points=self._key_points(topic, classification.keywords, classification.category),
            call_to_action=self._call_to_action(classification.category),
            platform_targets=self.settings.future_platform_targets,
            metadata={
                "planning_strategy": self.settings.planning_strategy,
                "topic_category": classification.category,
                "difficulty_level": classification.difficulty_level,
                "keywords": list(classification.keywords),
                "source": topic.source,
                "provider_name": topic.provider_name,
            },
        )
        self.logger.info(
            "plan_created",
            extra={
                "component": "planning",
                "topic_id": topic.id,
                "plan_id": plan.id,
                "version_number": plan.version_number,
                "persona": persona,
                "hook_style": hook_style,
                "visual_theme": visual_theme,
            },
        )
        self.logger.info("planner_completed", extra={"component": "planning", "topic_id": topic.id, "plan_id": plan.id})
        return plan

    def _visual_theme(self, category: str, *, seed: str, offset: int) -> str:
        preferred = {
            "Artificial Intelligence": ("Abstract AI", "Futuristic"),
            "Cloud Infrastructure": ("Blueprint", "Dark UI"),
            "Cybersecurity": ("Dark UI", "Blueprint"),
            "Developer Tools": ("Minimal Tech", "Dark UI"),
            "Startups": ("Clean Startup", "Corporate Illustration"),
            "Open Source": ("Minimal Tech", "Blueprint"),
        }.get(category, ())
        for theme in preferred:
            if theme in self.settings.visual_themes:
                return theme
        return choose_rotating(self.settings.visual_themes, seed=seed, offset=offset)

    @staticmethod
    def _primary_angle(topic: Topic, category: str) -> str:
        return f"What {topic.title} reveals about {category.lower()}"

    @staticmethod
    def _target_audience(category: str, difficulty_level: str) -> str:
        if category == "Startups":
            return "technical founders and product leaders"
        if difficulty_level == "introductory":
            return "curious builders learning the topic"
        if difficulty_level == "advanced":
            return "experienced engineers and technical decision-makers"
        return "software practitioners and technology leaders"

    @staticmethod
    def _content_goal(hook_style: str) -> str:
        if hook_style in {"Tutorial", "Mistake"}:
            return "teach a practical lesson"
        if hook_style in {"Contrarian Opinion", "Bold Statement"}:
            return "challenge a common assumption"
        if hook_style in {"Prediction", "Statistic"}:
            return "frame an emerging trend"
        return "spark useful reflection"

    @staticmethod
    def _content_type(hook_style: str) -> str:
        return {
            "Tutorial": "explainer",
            "Mistake": "lesson",
            "Comparison": "comparison",
            "Question": "discussion",
            "Story": "narrative",
        }.get(hook_style, "insight")

    @staticmethod
    def _image_prompt(topic: Topic, category: str, visual_theme: str) -> str:
        return f"{visual_theme} visual about {category.lower()}: {topic.title}"

    @staticmethod
    def _key_points(topic: Topic, keywords: tuple[str, ...], category: str) -> tuple[str, ...]:
        keyword_text = ", ".join(keywords[:3]) if keywords else category.lower()
        return (
            f"Context: {topic.title}",
            f"Why it matters for {category.lower()}",
            f"Key concepts to mention: {keyword_text}",
        )

    @staticmethod
    def _call_to_action(category: str) -> str:
        return f"Invite readers to consider how this changes their approach to {category.lower()}."


class ContentPlanningError(RuntimeError):
    """Raised when content planning cannot complete."""

