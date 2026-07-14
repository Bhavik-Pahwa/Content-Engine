"""Centralized application configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import os
import tomllib


class ConfigError(ValueError):
    """Raised when configuration is invalid."""


@dataclass(frozen=True)
class AppSettings:
    name: str = "content-engine"
    environment: str = "development"
    timezone: str = "Asia/Kolkata"
    idle_interval_seconds: int = 60


@dataclass(frozen=True)
class StorageSettings:
    root_dir: Path = Path("storage")
    cache_dir: Path = Path("storage/cache")
    images_dir: Path = Path("storage/images")
    assets_dir: Path = Path("storage/assets")
    temp_dir: Path = Path("storage/temp")


@dataclass(frozen=True)
class DatabaseSettings:
    path: Path = Path("storage/content_engine.sqlite3")


@dataclass(frozen=True)
class LoggingSettings:
    level: str = "INFO"
    directory: Path = Path("logs")
    app_log_name: str = "app.log"
    error_log_name: str = "error.log"
    max_bytes: int = 1_048_576
    backup_count: int = 5


@dataclass(frozen=True)
class RuntimeSettings:
    dry_run: bool = True
    publishing_paused: bool = True
    queue_target_size: int = 7
    scheduler_poll_interval_seconds: float = 5.0
    worker_concurrency: int = 2
    retry_delay_seconds: float = 60.0
    retry_backoff_multiplier: float = 2.0
    retry_max_delay_seconds: float = 3_600.0
    stale_job_timeout_seconds: float = 3_600.0


@dataclass(frozen=True)
class DiscoverySettings:
    enabled_topic_providers: tuple[str, ...] = ("hacker_news",)
    hacker_news_fetch_limit: int = 30
    hacker_news_request_timeout_seconds: float = 5.0
    hacker_news_retry_count: int = 2
    duplicate_title_similarity_threshold: float = 0.88
    allowed_categories: dict[str, tuple[str, ...]] | None = None


@dataclass(frozen=True)
class PlanningSettings:
    enabled_personas: tuple[str, ...] = ("Engineer", "Educator", "Founder", "Researcher", "Minimalist")
    hook_styles: tuple[str, ...] = (
        "Question",
        "Bold Statement",
        "Prediction",
        "Contrarian Opinion",
        "Story",
        "Statistic",
        "Tutorial",
        "Mistake",
        "Comparison",
    )
    visual_themes: tuple[str, ...] = (
        "Corporate Illustration",
        "Minimal Tech",
        "Futuristic",
        "Blueprint",
        "Abstract AI",
        "Dark UI",
        "Clean Startup",
    )
    planning_strategy: str = "deterministic"
    future_platform_targets: tuple[str, ...] = ("linkedin", "blog", "x")


@dataclass(frozen=True)
class KnowledgeSettings:
    request_timeout_seconds: float = 8.0
    retry_count: int = 2
    max_download_bytes: int = 2_000_000
    store_raw_html: bool = True
    min_clean_text_words: int = 80
    user_agent: str = "ContentEngine/0.1 (+local knowledge extraction)"


@dataclass(frozen=True)
class WritingSettings:
    prompt_dir: Path = Path("prompts")
    enabled_platform_writers: tuple[str, ...] = ("linkedin",)
    llm_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/free"
    openrouter_timeout_seconds: float = 30.0
    generation_retry_limit: int = 2
    min_post_characters: int = 450
    max_post_characters: int = 1_800
    banned_phrases: tuple[str, ...] = (
        "in today's fast-paced world",
        "game changer",
        "revolutionize",
        "unlock the power",
        "delve into",
        "it's not just",
    )
    max_hashtags: int = 5
    allow_emojis: bool = False


@dataclass(frozen=True)
class ImageSettings:
    provider: str = "local_template"
    model: str = "local-template-v2"
    width: int = 1200
    height: int = 627
    retry_limit: int = 1
    reuse_cached_images: bool = True
    prompt_version: str = "1.1.0"
    negative_prompt: str = "low quality, blurry, distorted text, watermark, logo, faces, hands, clutter"
    stable_diffusion_base_url: str = "http://127.0.0.1:7860"
    stable_diffusion_timeout_seconds: float = 180.0
    stable_diffusion_steps: int = 24
    stable_diffusion_cfg_scale: float = 6.5
    stable_diffusion_sampler_name: str = "DPM++ 2M Karras"
    stable_diffusion_fallback_to_template: bool = True
    diffusers_model_id: str = "runwayml/stable-diffusion-v1-5"
    diffusers_steps: int = 24
    diffusers_guidance_scale: float = 6.5
    diffusers_generation_width: int = 768
    diffusers_generation_height: int = 400


@dataclass(frozen=True)
class PublishingSettings:
    provider: str = "linkedin"
    linkedin_session_dir: Path = Path("storage/browser/linkedin")
    screenshot_dir: Path = Path("storage/screenshots")
    linkedin_author_name: str = "Bhavik Pahwa"
    linkedin_target_page_name: str | None = "First Hand Devs | FHD"
    headless: bool = True
    timeout_seconds: float = 30.0
    require_image: bool = False
    publish_retry_limit: int = 1
    simulate: bool = False


@dataclass(frozen=True)
class Settings:
    app: AppSettings
    storage: StorageSettings
    database: DatabaseSettings
    logging: LoggingSettings
    runtime: RuntimeSettings
    discovery: DiscoverySettings
    planning: PlanningSettings
    knowledge: KnowledgeSettings
    writing: WritingSettings
    image: ImageSettings
    publishing: PublishingSettings


def load_settings(
    config_path: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    base_dir: Path | None = None,
) -> Settings:
    root = (base_dir or Path.cwd()).resolve()
    environment = _environment_with_dotenv(env, root)
    selected_path = _select_config_path(config_path, environment, root)
    file_values = _load_toml(selected_path) if selected_path else {}

    app = AppSettings(
        name=_str_value(file_values, ("app", "name"), "CONTENT_ENGINE_APP_NAME", environment, AppSettings.name),
        environment=_str_value(
            file_values,
            ("app", "environment"),
            "CONTENT_ENGINE_ENVIRONMENT",
            environment,
            AppSettings.environment,
        ),
        timezone=_str_value(
            file_values,
            ("app", "timezone"),
            "CONTENT_ENGINE_TIMEZONE",
            environment,
            AppSettings.timezone,
        ),
        idle_interval_seconds=_int_value(
            file_values,
            ("app", "idle_interval_seconds"),
            "CONTENT_ENGINE_IDLE_INTERVAL_SECONDS",
            environment,
            AppSettings.idle_interval_seconds,
        ),
    )
    storage = StorageSettings(
        root_dir=_path_value(file_values, ("storage", "root_dir"), "CONTENT_ENGINE_STORAGE_DIR", environment, StorageSettings.root_dir, root),
        cache_dir=_path_value(file_values, ("storage", "cache_dir"), "CONTENT_ENGINE_CACHE_DIR", environment, StorageSettings.cache_dir, root),
        images_dir=_path_value(file_values, ("storage", "images_dir"), "CONTENT_ENGINE_IMAGES_DIR", environment, StorageSettings.images_dir, root),
        assets_dir=_path_value(file_values, ("storage", "assets_dir"), "CONTENT_ENGINE_ASSETS_DIR", environment, StorageSettings.assets_dir, root),
        temp_dir=_path_value(file_values, ("storage", "temp_dir"), "CONTENT_ENGINE_TEMP_DIR", environment, StorageSettings.temp_dir, root),
    )
    database = DatabaseSettings(
        path=_path_value(file_values, ("database", "path"), "CONTENT_ENGINE_DATABASE_PATH", environment, DatabaseSettings.path, root)
    )
    logging_settings = LoggingSettings(
        level=_str_value(file_values, ("logging", "level"), "CONTENT_ENGINE_LOG_LEVEL", environment, LoggingSettings.level).upper(),
        directory=_path_value(file_values, ("logging", "directory"), "CONTENT_ENGINE_LOG_DIR", environment, LoggingSettings.directory, root),
        app_log_name=_str_value(
            file_values,
            ("logging", "app_log_name"),
            "CONTENT_ENGINE_APP_LOG_NAME",
            environment,
            LoggingSettings.app_log_name,
        ),
        error_log_name=_str_value(
            file_values,
            ("logging", "error_log_name"),
            "CONTENT_ENGINE_ERROR_LOG_NAME",
            environment,
            LoggingSettings.error_log_name,
        ),
        max_bytes=_int_value(
            file_values,
            ("logging", "max_bytes"),
            "CONTENT_ENGINE_LOG_MAX_BYTES",
            environment,
            LoggingSettings.max_bytes,
        ),
        backup_count=_int_value(
            file_values,
            ("logging", "backup_count"),
            "CONTENT_ENGINE_LOG_BACKUP_COUNT",
            environment,
            LoggingSettings.backup_count,
        ),
    )
    runtime = RuntimeSettings(
        dry_run=_bool_value(file_values, ("runtime", "dry_run"), "CONTENT_ENGINE_DRY_RUN", environment, RuntimeSettings.dry_run),
        publishing_paused=_bool_value(
            file_values,
            ("runtime", "publishing_paused"),
            "CONTENT_ENGINE_PUBLISHING_PAUSED",
            environment,
            RuntimeSettings.publishing_paused,
        ),
        queue_target_size=_int_value(
            file_values,
            ("runtime", "queue_target_size"),
            "CONTENT_ENGINE_QUEUE_TARGET_SIZE",
            environment,
            RuntimeSettings.queue_target_size,
        ),
        scheduler_poll_interval_seconds=_float_value(
            file_values,
            ("runtime", "scheduler_poll_interval_seconds"),
            "CONTENT_ENGINE_SCHEDULER_POLL_INTERVAL_SECONDS",
            environment,
            RuntimeSettings.scheduler_poll_interval_seconds,
        ),
        worker_concurrency=_int_value(
            file_values,
            ("runtime", "worker_concurrency"),
            "CONTENT_ENGINE_WORKER_CONCURRENCY",
            environment,
            RuntimeSettings.worker_concurrency,
        ),
        retry_delay_seconds=_float_value(
            file_values,
            ("runtime", "retry_delay_seconds"),
            "CONTENT_ENGINE_RETRY_DELAY_SECONDS",
            environment,
            RuntimeSettings.retry_delay_seconds,
        ),
        retry_backoff_multiplier=_float_value(
            file_values,
            ("runtime", "retry_backoff_multiplier"),
            "CONTENT_ENGINE_RETRY_BACKOFF_MULTIPLIER",
            environment,
            RuntimeSettings.retry_backoff_multiplier,
        ),
        retry_max_delay_seconds=_float_value(
            file_values,
            ("runtime", "retry_max_delay_seconds"),
            "CONTENT_ENGINE_RETRY_MAX_DELAY_SECONDS",
            environment,
            RuntimeSettings.retry_max_delay_seconds,
        ),
        stale_job_timeout_seconds=_float_value(
            file_values,
            ("runtime", "stale_job_timeout_seconds"),
            "CONTENT_ENGINE_STALE_JOB_TIMEOUT_SECONDS",
            environment,
            RuntimeSettings.stale_job_timeout_seconds,
        ),
    )
    discovery = DiscoverySettings(
        enabled_topic_providers=_tuple_value(
            file_values,
            ("discovery", "enabled_topic_providers"),
            "CONTENT_ENGINE_TOPIC_PROVIDERS",
            environment,
            DiscoverySettings.enabled_topic_providers,
        ),
        hacker_news_fetch_limit=_int_value(
            file_values,
            ("discovery", "hacker_news_fetch_limit"),
            "CONTENT_ENGINE_HN_FETCH_LIMIT",
            environment,
            DiscoverySettings.hacker_news_fetch_limit,
        ),
        hacker_news_request_timeout_seconds=_float_value(
            file_values,
            ("discovery", "hacker_news_request_timeout_seconds"),
            "CONTENT_ENGINE_HN_REQUEST_TIMEOUT_SECONDS",
            environment,
            DiscoverySettings.hacker_news_request_timeout_seconds,
        ),
        hacker_news_retry_count=_int_value(
            file_values,
            ("discovery", "hacker_news_retry_count"),
            "CONTENT_ENGINE_HN_RETRY_COUNT",
            environment,
            DiscoverySettings.hacker_news_retry_count,
        ),
        duplicate_title_similarity_threshold=_float_value(
            file_values,
            ("discovery", "duplicate_title_similarity_threshold"),
            "CONTENT_ENGINE_DUPLICATE_TITLE_SIMILARITY_THRESHOLD",
            environment,
            DiscoverySettings.duplicate_title_similarity_threshold,
        ),
        allowed_categories=_category_keywords(file_values),
    )
    planning = PlanningSettings(
        enabled_personas=_tuple_value(
            file_values,
            ("planning", "enabled_personas"),
            "CONTENT_ENGINE_PLANNING_PERSONAS",
            environment,
            PlanningSettings.enabled_personas,
        ),
        hook_styles=_tuple_value(
            file_values,
            ("planning", "hook_styles"),
            "CONTENT_ENGINE_PLANNING_HOOK_STYLES",
            environment,
            PlanningSettings.hook_styles,
        ),
        visual_themes=_tuple_value(
            file_values,
            ("planning", "visual_themes"),
            "CONTENT_ENGINE_PLANNING_VISUAL_THEMES",
            environment,
            PlanningSettings.visual_themes,
        ),
        planning_strategy=_str_value(
            file_values,
            ("planning", "planning_strategy"),
            "CONTENT_ENGINE_PLANNING_STRATEGY",
            environment,
            PlanningSettings.planning_strategy,
        ),
        future_platform_targets=_tuple_value(
            file_values,
            ("planning", "future_platform_targets"),
            "CONTENT_ENGINE_PLANNING_PLATFORM_TARGETS",
            environment,
            PlanningSettings.future_platform_targets,
        ),
    )
    knowledge = KnowledgeSettings(
        request_timeout_seconds=_float_value(
            file_values,
            ("knowledge", "request_timeout_seconds"),
            "CONTENT_ENGINE_KNOWLEDGE_REQUEST_TIMEOUT_SECONDS",
            environment,
            KnowledgeSettings.request_timeout_seconds,
        ),
        retry_count=_int_value(
            file_values,
            ("knowledge", "retry_count"),
            "CONTENT_ENGINE_KNOWLEDGE_RETRY_COUNT",
            environment,
            KnowledgeSettings.retry_count,
        ),
        max_download_bytes=_int_value(
            file_values,
            ("knowledge", "max_download_bytes"),
            "CONTENT_ENGINE_KNOWLEDGE_MAX_DOWNLOAD_BYTES",
            environment,
            KnowledgeSettings.max_download_bytes,
        ),
        store_raw_html=_bool_value(
            file_values,
            ("knowledge", "store_raw_html"),
            "CONTENT_ENGINE_KNOWLEDGE_STORE_RAW_HTML",
            environment,
            KnowledgeSettings.store_raw_html,
        ),
        min_clean_text_words=_int_value(
            file_values,
            ("knowledge", "min_clean_text_words"),
            "CONTENT_ENGINE_KNOWLEDGE_MIN_CLEAN_TEXT_WORDS",
            environment,
            KnowledgeSettings.min_clean_text_words,
        ),
        user_agent=_str_value(
            file_values,
            ("knowledge", "user_agent"),
            "CONTENT_ENGINE_KNOWLEDGE_USER_AGENT",
            environment,
            KnowledgeSettings.user_agent,
        ),
    )
    writing = WritingSettings(
        prompt_dir=_path_value(
            file_values,
            ("writing", "prompt_dir"),
            "CONTENT_ENGINE_PROMPT_DIR",
            environment,
            WritingSettings.prompt_dir,
            root,
        ),
        enabled_platform_writers=_tuple_value(
            file_values,
            ("writing", "enabled_platform_writers"),
            "CONTENT_ENGINE_ENABLED_WRITERS",
            environment,
            WritingSettings.enabled_platform_writers,
        ),
        llm_provider=_str_value(
            file_values,
            ("writing", "llm_provider"),
            "CONTENT_ENGINE_LLM_PROVIDER",
            environment,
            WritingSettings.llm_provider,
        ),
        openrouter_api_key=_optional_str_value(
            file_values,
            ("writing", "openrouter_api_key"),
            "OPENROUTER_API_KEY",
            environment,
            WritingSettings.openrouter_api_key,
        ),
        openrouter_model=_str_value(
            file_values,
            ("writing", "openrouter_model"),
            "CONTENT_ENGINE_OPENROUTER_MODEL",
            environment,
            WritingSettings.openrouter_model,
        ),
        openrouter_timeout_seconds=_float_value(
            file_values,
            ("writing", "openrouter_timeout_seconds"),
            "CONTENT_ENGINE_OPENROUTER_TIMEOUT_SECONDS",
            environment,
            WritingSettings.openrouter_timeout_seconds,
        ),
        generation_retry_limit=_int_value(
            file_values,
            ("writing", "generation_retry_limit"),
            "CONTENT_ENGINE_WRITING_RETRY_LIMIT",
            environment,
            WritingSettings.generation_retry_limit,
        ),
        min_post_characters=_int_value(
            file_values,
            ("writing", "min_post_characters"),
            "CONTENT_ENGINE_MIN_POST_CHARACTERS",
            environment,
            WritingSettings.min_post_characters,
        ),
        max_post_characters=_int_value(
            file_values,
            ("writing", "max_post_characters"),
            "CONTENT_ENGINE_MAX_POST_CHARACTERS",
            environment,
            WritingSettings.max_post_characters,
        ),
        banned_phrases=_tuple_value(
            file_values,
            ("writing", "banned_phrases"),
            "CONTENT_ENGINE_BANNED_PHRASES",
            environment,
            WritingSettings.banned_phrases,
        ),
        max_hashtags=_int_value(
            file_values,
            ("writing", "max_hashtags"),
            "CONTENT_ENGINE_MAX_HASHTAGS",
            environment,
            WritingSettings.max_hashtags,
        ),
        allow_emojis=_bool_value(
            file_values,
            ("writing", "allow_emojis"),
            "CONTENT_ENGINE_ALLOW_EMOJIS",
            environment,
            WritingSettings.allow_emojis,
        ),
    )
    image = ImageSettings(
        provider=_str_value(file_values, ("image", "provider"), "CONTENT_ENGINE_IMAGE_PROVIDER", environment, ImageSettings.provider),
        model=_str_value(file_values, ("image", "model"), "CONTENT_ENGINE_IMAGE_MODEL", environment, ImageSettings.model),
        width=_int_value(file_values, ("image", "width"), "CONTENT_ENGINE_IMAGE_WIDTH", environment, ImageSettings.width),
        height=_int_value(file_values, ("image", "height"), "CONTENT_ENGINE_IMAGE_HEIGHT", environment, ImageSettings.height),
        retry_limit=_int_value(
            file_values,
            ("image", "retry_limit"),
            "CONTENT_ENGINE_IMAGE_RETRY_LIMIT",
            environment,
            ImageSettings.retry_limit,
        ),
        reuse_cached_images=_bool_value(
            file_values,
            ("image", "reuse_cached_images"),
            "CONTENT_ENGINE_REUSE_CACHED_IMAGES",
            environment,
            ImageSettings.reuse_cached_images,
        ),
        prompt_version=_str_value(
            file_values,
            ("image", "prompt_version"),
            "CONTENT_ENGINE_IMAGE_PROMPT_VERSION",
            environment,
            ImageSettings.prompt_version,
        ),
        negative_prompt=_str_value(
            file_values,
            ("image", "negative_prompt"),
            "CONTENT_ENGINE_IMAGE_NEGATIVE_PROMPT",
            environment,
            ImageSettings.negative_prompt,
        ),
        stable_diffusion_base_url=_str_value(
            file_values,
            ("image", "stable_diffusion_base_url"),
            "CONTENT_ENGINE_SD_BASE_URL",
            environment,
            ImageSettings.stable_diffusion_base_url,
        ),
        stable_diffusion_timeout_seconds=_float_value(
            file_values,
            ("image", "stable_diffusion_timeout_seconds"),
            "CONTENT_ENGINE_SD_TIMEOUT_SECONDS",
            environment,
            ImageSettings.stable_diffusion_timeout_seconds,
        ),
        stable_diffusion_steps=_int_value(
            file_values,
            ("image", "stable_diffusion_steps"),
            "CONTENT_ENGINE_SD_STEPS",
            environment,
            ImageSettings.stable_diffusion_steps,
        ),
        stable_diffusion_cfg_scale=_float_value(
            file_values,
            ("image", "stable_diffusion_cfg_scale"),
            "CONTENT_ENGINE_SD_CFG_SCALE",
            environment,
            ImageSettings.stable_diffusion_cfg_scale,
        ),
        stable_diffusion_sampler_name=_str_value(
            file_values,
            ("image", "stable_diffusion_sampler_name"),
            "CONTENT_ENGINE_SD_SAMPLER_NAME",
            environment,
            ImageSettings.stable_diffusion_sampler_name,
        ),
        stable_diffusion_fallback_to_template=_bool_value(
            file_values,
            ("image", "stable_diffusion_fallback_to_template"),
            "CONTENT_ENGINE_SD_FALLBACK_TO_TEMPLATE",
            environment,
            ImageSettings.stable_diffusion_fallback_to_template,
        ),
        diffusers_model_id=_str_value(
            file_values,
            ("image", "diffusers_model_id"),
            "CONTENT_ENGINE_DIFFUSERS_MODEL_ID",
            environment,
            ImageSettings.diffusers_model_id,
        ),
        diffusers_steps=_int_value(
            file_values,
            ("image", "diffusers_steps"),
            "CONTENT_ENGINE_DIFFUSERS_STEPS",
            environment,
            ImageSettings.diffusers_steps,
        ),
        diffusers_guidance_scale=_float_value(
            file_values,
            ("image", "diffusers_guidance_scale"),
            "CONTENT_ENGINE_DIFFUSERS_GUIDANCE_SCALE",
            environment,
            ImageSettings.diffusers_guidance_scale,
        ),
        diffusers_generation_width=_int_value(
            file_values,
            ("image", "diffusers_generation_width"),
            "CONTENT_ENGINE_DIFFUSERS_WIDTH",
            environment,
            ImageSettings.diffusers_generation_width,
        ),
        diffusers_generation_height=_int_value(
            file_values,
            ("image", "diffusers_generation_height"),
            "CONTENT_ENGINE_DIFFUSERS_HEIGHT",
            environment,
            ImageSettings.diffusers_generation_height,
        ),
    )
    publishing = PublishingSettings(
        provider=_str_value(
            file_values,
            ("publishing", "provider"),
            "CONTENT_ENGINE_PUBLISHING_PROVIDER",
            environment,
            PublishingSettings.provider,
        ),
        linkedin_session_dir=_path_value(
            file_values,
            ("publishing", "linkedin_session_dir"),
            "CONTENT_ENGINE_LINKEDIN_SESSION_DIR",
            environment,
            PublishingSettings.linkedin_session_dir,
            root,
        ),
        screenshot_dir=_path_value(
            file_values,
            ("publishing", "screenshot_dir"),
            "CONTENT_ENGINE_PUBLISHING_SCREENSHOT_DIR",
            environment,
            PublishingSettings.screenshot_dir,
            root,
        ),
        linkedin_author_name=_str_value(
            file_values,
            ("publishing", "linkedin_author_name"),
            "CONTENT_ENGINE_LINKEDIN_AUTHOR_NAME",
            environment,
            PublishingSettings.linkedin_author_name,
        ),
        linkedin_target_page_name=_optional_str_value(
            file_values,
            ("publishing", "linkedin_target_page_name"),
            "CONTENT_ENGINE_LINKEDIN_TARGET_PAGE_NAME",
            environment,
            PublishingSettings.linkedin_target_page_name,
        ),
        headless=_bool_value(
            file_values,
            ("publishing", "headless"),
            "CONTENT_ENGINE_PUBLISHING_HEADLESS",
            environment,
            PublishingSettings.headless,
        ),
        timeout_seconds=_float_value(
            file_values,
            ("publishing", "timeout_seconds"),
            "CONTENT_ENGINE_PUBLISHING_TIMEOUT_SECONDS",
            environment,
            PublishingSettings.timeout_seconds,
        ),
        require_image=_bool_value(
            file_values,
            ("publishing", "require_image"),
            "CONTENT_ENGINE_PUBLISHING_REQUIRE_IMAGE",
            environment,
            PublishingSettings.require_image,
        ),
        publish_retry_limit=_int_value(
            file_values,
            ("publishing", "publish_retry_limit"),
            "CONTENT_ENGINE_PUBLISHING_RETRY_LIMIT",
            environment,
            PublishingSettings.publish_retry_limit,
        ),
        simulate=_bool_value(
            file_values,
            ("publishing", "simulate"),
            "CONTENT_ENGINE_PUBLISHING_SIMULATE",
            environment,
            PublishingSettings.simulate,
        ),
    )
    settings = Settings(
        app=app,
        storage=storage,
        database=database,
        logging=logging_settings,
        runtime=runtime,
        discovery=discovery,
        planning=planning,
        knowledge=knowledge,
        writing=writing,
        image=image,
        publishing=publishing,
    )
    _validate(settings)
    return settings


def _environment_with_dotenv(env: Mapping[str, str] | None, base_dir: Path) -> Mapping[str, str]:
    if env is not None:
        return env
    values = dict(os.environ)
    dotenv_path = base_dir / ".env"
    if not dotenv_path.exists():
        return values
    values.update(_load_dotenv(dotenv_path, values))
    return values


def _load_dotenv(path: Path, existing: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in existing:
            continue
        result[key] = _clean_dotenv_value(value.strip())
    return result


def _clean_dotenv_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _select_config_path(config_path: Path | None, env: Mapping[str, str], base_dir: Path) -> Path | None:
    candidate = config_path or (Path(env["CONTENT_ENGINE_CONFIG"]) if env.get("CONTENT_ENGINE_CONFIG") else None)
    if candidate is not None:
        resolved = candidate if candidate.is_absolute() else base_dir / candidate
        if not resolved.exists():
            raise ConfigError(f"Configuration file does not exist: {resolved}")
        return resolved
    default_path = base_dir / "config.toml"
    return default_path if default_path.exists() else None


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML configuration: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration root must be a table: {path}")
    return data


def _nested(config: Mapping[str, Any], keys: tuple[str, str], default: Any) -> Any:
    section = config.get(keys[0], {})
    if not isinstance(section, Mapping):
        raise ConfigError(f"Configuration section [{keys[0]}] must be a table")
    return section.get(keys[1], default)


def _str_value(config: Mapping[str, Any], keys: tuple[str, str], env_name: str, env: Mapping[str, str], default: str) -> str:
    value = env.get(env_name, _nested(config, keys, default))
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{env_name} must be a non-empty string")
    return value.strip()


def _optional_str_value(
    config: Mapping[str, Any],
    keys: tuple[str, str],
    env_name: str,
    env: Mapping[str, str],
    default: str | None,
) -> str | None:
    value = env.get(env_name, _nested(config, keys, default))
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{env_name} must be a string")
    stripped = value.strip()
    return stripped or None


def _int_value(config: Mapping[str, Any], keys: tuple[str, str], env_name: str, env: Mapping[str, str], default: int) -> int:
    raw = env.get(env_name, _nested(config, keys, default))
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{env_name} must be an integer") from exc


def _float_value(config: Mapping[str, Any], keys: tuple[str, str], env_name: str, env: Mapping[str, str], default: float) -> float:
    raw = env.get(env_name, _nested(config, keys, default))
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{env_name} must be a number") from exc


def _bool_value(config: Mapping[str, Any], keys: tuple[str, str], env_name: str, env: Mapping[str, str], default: bool) -> bool:
    raw = env.get(env_name, _nested(config, keys, default))
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ConfigError(f"{env_name} must be a boolean")


def _tuple_value(
    config: Mapping[str, Any],
    keys: tuple[str, str],
    env_name: str,
    env: Mapping[str, str],
    default: tuple[str, ...],
) -> tuple[str, ...]:
    raw = env.get(env_name)
    if raw is not None:
        values = tuple(item.strip() for item in raw.split(",") if item.strip())
    else:
        configured = _nested(config, keys, default)
        if isinstance(configured, str):
            values = (configured.strip(),)
        elif isinstance(configured, list):
            values = tuple(str(item).strip() for item in configured if str(item).strip())
        elif isinstance(configured, tuple):
            values = tuple(str(item).strip() for item in configured if str(item).strip())
        else:
            raise ConfigError(f"{env_name} must be a comma-separated string or TOML array")
    if not values:
        raise ConfigError(f"{env_name} must contain at least one value")
    return values


def _category_keywords(config: Mapping[str, Any]) -> dict[str, tuple[str, ...]] | None:
    discovery = config.get("discovery", {})
    if not isinstance(discovery, Mapping):
        raise ConfigError("Configuration section [discovery] must be a table")
    categories = discovery.get("allowed_categories")
    if categories is None:
        return None
    if not isinstance(categories, Mapping):
        raise ConfigError("discovery.allowed_categories must be a table")
    result: dict[str, tuple[str, ...]] = {}
    for category, keywords in categories.items():
        if not isinstance(keywords, list):
            raise ConfigError("Each discovery.allowed_categories value must be a TOML array")
        values = tuple(str(keyword).strip().lower() for keyword in keywords if str(keyword).strip())
        if values:
            result[str(category).strip()] = values
    if not result:
        raise ConfigError("discovery.allowed_categories must contain at least one keyword")
    return result


def _path_value(
    config: Mapping[str, Any],
    keys: tuple[str, str],
    env_name: str,
    env: Mapping[str, str],
    default: Path,
    base_dir: Path,
) -> Path:
    raw = env.get(env_name, _nested(config, keys, default))
    path = raw if isinstance(raw, Path) else Path(str(raw))
    return path if path.is_absolute() else base_dir / path


def _validate(settings: Settings) -> None:
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if settings.logging.level not in valid_levels:
        raise ConfigError(f"CONTENT_ENGINE_LOG_LEVEL must be one of {sorted(valid_levels)}")
    if settings.app.idle_interval_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_IDLE_INTERVAL_SECONDS must be greater than zero")
    if settings.runtime.queue_target_size <= 0:
        raise ConfigError("CONTENT_ENGINE_QUEUE_TARGET_SIZE must be greater than zero")
    if settings.runtime.worker_concurrency <= 0:
        raise ConfigError("CONTENT_ENGINE_WORKER_CONCURRENCY must be greater than zero")
    if settings.runtime.scheduler_poll_interval_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_SCHEDULER_POLL_INTERVAL_SECONDS must be greater than zero")
    if settings.runtime.retry_delay_seconds < 0:
        raise ConfigError("CONTENT_ENGINE_RETRY_DELAY_SECONDS cannot be negative")
    if settings.runtime.retry_backoff_multiplier < 1:
        raise ConfigError("CONTENT_ENGINE_RETRY_BACKOFF_MULTIPLIER must be at least one")
    if settings.runtime.retry_max_delay_seconds < settings.runtime.retry_delay_seconds:
        raise ConfigError("CONTENT_ENGINE_RETRY_MAX_DELAY_SECONDS must be greater than or equal to retry delay")
    if settings.runtime.stale_job_timeout_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_STALE_JOB_TIMEOUT_SECONDS must be greater than zero")
    if settings.discovery.hacker_news_fetch_limit <= 0:
        raise ConfigError("CONTENT_ENGINE_HN_FETCH_LIMIT must be greater than zero")
    if settings.discovery.hacker_news_request_timeout_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_HN_REQUEST_TIMEOUT_SECONDS must be greater than zero")
    if settings.discovery.hacker_news_retry_count < 0:
        raise ConfigError("CONTENT_ENGINE_HN_RETRY_COUNT cannot be negative")
    if not 0 <= settings.discovery.duplicate_title_similarity_threshold <= 1:
        raise ConfigError("CONTENT_ENGINE_DUPLICATE_TITLE_SIMILARITY_THRESHOLD must be between 0 and 1")
    if settings.planning.planning_strategy != "deterministic":
        raise ConfigError("CONTENT_ENGINE_PLANNING_STRATEGY currently supports only 'deterministic'")
    if settings.knowledge.request_timeout_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_KNOWLEDGE_REQUEST_TIMEOUT_SECONDS must be greater than zero")
    if settings.knowledge.retry_count < 0:
        raise ConfigError("CONTENT_ENGINE_KNOWLEDGE_RETRY_COUNT cannot be negative")
    if settings.knowledge.max_download_bytes <= 0:
        raise ConfigError("CONTENT_ENGINE_KNOWLEDGE_MAX_DOWNLOAD_BYTES must be greater than zero")
    if settings.knowledge.min_clean_text_words <= 0:
        raise ConfigError("CONTENT_ENGINE_KNOWLEDGE_MIN_CLEAN_TEXT_WORDS must be greater than zero")
    if settings.writing.llm_provider != "openrouter":
        raise ConfigError("CONTENT_ENGINE_LLM_PROVIDER currently supports only 'openrouter'")
    if "linkedin" not in {writer.lower() for writer in settings.writing.enabled_platform_writers}:
        raise ConfigError("CONTENT_ENGINE_ENABLED_WRITERS must include 'linkedin'")
    if settings.writing.openrouter_timeout_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_OPENROUTER_TIMEOUT_SECONDS must be greater than zero")
    if settings.writing.generation_retry_limit < 0:
        raise ConfigError("CONTENT_ENGINE_WRITING_RETRY_LIMIT cannot be negative")
    if settings.writing.min_post_characters <= 0:
        raise ConfigError("CONTENT_ENGINE_MIN_POST_CHARACTERS must be greater than zero")
    if settings.writing.max_post_characters < settings.writing.min_post_characters:
        raise ConfigError("CONTENT_ENGINE_MAX_POST_CHARACTERS must be greater than or equal to minimum length")
    if settings.writing.max_hashtags < 0:
        raise ConfigError("CONTENT_ENGINE_MAX_HASHTAGS cannot be negative")
    valid_image_providers = {"local_template", "stable_diffusion_webui", "stable_diffusion", "sd_webui", "sd", "local_diffusers", "diffusers"}
    if settings.image.provider not in valid_image_providers:
        raise ConfigError(f"CONTENT_ENGINE_IMAGE_PROVIDER must be one of {sorted(valid_image_providers)}")
    if settings.image.width <= 0:
        raise ConfigError("CONTENT_ENGINE_IMAGE_WIDTH must be greater than zero")
    if settings.image.height <= 0:
        raise ConfigError("CONTENT_ENGINE_IMAGE_HEIGHT must be greater than zero")
    if settings.image.retry_limit < 0:
        raise ConfigError("CONTENT_ENGINE_IMAGE_RETRY_LIMIT cannot be negative")
    if settings.image.stable_diffusion_timeout_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_SD_TIMEOUT_SECONDS must be greater than zero")
    if settings.image.stable_diffusion_steps <= 0:
        raise ConfigError("CONTENT_ENGINE_SD_STEPS must be greater than zero")
    if settings.image.stable_diffusion_cfg_scale <= 0:
        raise ConfigError("CONTENT_ENGINE_SD_CFG_SCALE must be greater than zero")
    if settings.image.diffusers_steps <= 0:
        raise ConfigError("CONTENT_ENGINE_DIFFUSERS_STEPS must be greater than zero")
    if settings.image.diffusers_guidance_scale <= 0:
        raise ConfigError("CONTENT_ENGINE_DIFFUSERS_GUIDANCE_SCALE must be greater than zero")
    if settings.image.diffusers_generation_width <= 0:
        raise ConfigError("CONTENT_ENGINE_DIFFUSERS_WIDTH must be greater than zero")
    if settings.image.diffusers_generation_height <= 0:
        raise ConfigError("CONTENT_ENGINE_DIFFUSERS_HEIGHT must be greater than zero")
    if settings.publishing.provider != "linkedin":
        raise ConfigError("CONTENT_ENGINE_PUBLISHING_PROVIDER currently supports only 'linkedin'")
    if settings.publishing.timeout_seconds <= 0:
        raise ConfigError("CONTENT_ENGINE_PUBLISHING_TIMEOUT_SECONDS must be greater than zero")
    if settings.publishing.publish_retry_limit < 0:
        raise ConfigError("CONTENT_ENGINE_PUBLISHING_RETRY_LIMIT cannot be negative")
    if settings.logging.max_bytes <= 0:
        raise ConfigError("CONTENT_ENGINE_LOG_MAX_BYTES must be greater than zero")
    if settings.logging.backup_count <= 0:
        raise ConfigError("CONTENT_ENGINE_LOG_BACKUP_COUNT must be greater than zero")
    if settings.database.path.exists() and settings.database.path.is_dir():
        raise ConfigError(f"Database path cannot be a directory: {settings.database.path}")
