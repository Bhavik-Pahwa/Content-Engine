"""Application runtime orchestration."""

from __future__ import annotations

from pathlib import Path
import signal
import time

from content_engine.app.autopost import AutopostRunner, default_delay_seconds, default_max_consecutive_failures
from content_engine.app.demo import print_demo_failure, print_demo_report, run_demo_pipeline
from content_engine.app.health import print_startup_summary, run_diagnostics
from content_engine.app.reports import build_report
from content_engine.config import ConfigError, load_settings
from content_engine.db import Database, MigrationRunner
from content_engine.domain import ArtifactType, ContentItemStage, PublishingStatus
from content_engine.observability import configure_logging
from content_engine.publishing import LinkedInPublisher
from content_engine.services import ServiceContainer, build_service_container
from content_engine.storage import initialize_storage


def initialize_application(config_path: Path | None = None) -> ServiceContainer:
    settings = load_settings(config_path=config_path)
    storage_paths = initialize_storage(settings.storage, settings.logging, settings.publishing)
    logger = configure_logging(settings.logging)
    database = Database(settings.database.path)
    migrations = MigrationRunner(database)
    applied = migrations.apply()
    if applied:
        logger.info("database_migrations_applied", extra={"component": "database", "migrations": applied})
    else:
        logger.info("database_migrations_current", extra={"component": "database"})
    return build_service_container(
        settings=settings,
        logger=logger,
        storage_paths=storage_paths,
        database=database,
        migrations=migrations,
    )


def run_health_check(config_path: Path | None = None) -> int:
    try:
        container = initialize_application(config_path=config_path)
        report = run_diagnostics(container)
        print_startup_summary(container, report)
        return 0 if report.ok else 1
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2


def run_demo(config_path: Path | None = None) -> int:
    try:
        container = initialize_application(config_path=config_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2

    report = run_diagnostics(container)
    if not report.ok:
        print_startup_summary(container, report)
        container.logger.error("demo_startup_diagnostics_failed", extra={"component": "demo"})
        return 1
    try:
        result = run_demo_pipeline(container)
    except Exception as exc:
        container.logger.exception("demo_pipeline_failed", extra={"component": "demo"})
        print_demo_failure(exc)
        return 1
    print_demo_report(result)
    return 0


def run_report(
    command: str,
    *,
    config_path: Path | None = None,
    identifier: str | None = None,
    limit: int = 20,
) -> int:
    try:
        container = initialize_application(config_path=config_path)
        report = build_report(container, command=command, identifier=identifier, limit=limit)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2
    except Exception as exc:
        print(f"Report error: {exc}", flush=True)
        return 1
    report.print()
    return 0


def run_publish(config_path: Path | None = None) -> int:
    try:
        container = initialize_application(config_path=config_path)
        artifact = container.publishing.publish_next()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2
    except Exception as exc:
        print("=" * 50)
        print("PUBLISH FAILED")
        print("=" * 50)
        print()
        print(str(exc))
        print()
        print("Completed artifacts and failed publication attempts were preserved.")
        print("=" * 50)
        return 1
    if artifact is None:
        print("No READY_TO_PUBLISH content item found.", flush=True)
        return 0
    if artifact.status == PublishingStatus.PUBLISHED:
        container.pipeline.record_artifact(
            content_item_id=artifact.content_item_id,
            artifact_type=ArtifactType.PUBLISHING,
            artifact_id=artifact.id,
            metadata={"platform": artifact.platform.value, "url": artifact.url},
            schedule_next=False,
        )
    print("=" * 50)
    print("PUBLISH COMPLETE")
    print("=" * 50)
    print()
    print(f"Content Item: {artifact.content_item_id}")
    print(f"Status: {artifact.status.value}")
    print(f"Platform: {artifact.platform.value}")
    if artifact.url:
        print(f"URL: {artifact.url}")
    if artifact.error:
        print(f"Note: {artifact.error}")
    print(f"Duration: {artifact.duration_seconds:.2f} seconds")
    print("=" * 50)
    return 0


def run_mark_ready(config_path: Path | None = None, *, identifier: str | None = None) -> int:
    try:
        container = initialize_application(config_path=config_path)
        content_item_id = identifier or _latest_image_ready_content_item_id(container)
        if content_item_id is None:
            print("No IMAGE_READY content item found.", flush=True)
            return 0
        item = container.repositories.content_items.required(content_item_id)
        if item.stage == ContentItemStage.READY_TO_PUBLISH:
            updated = item
        else:
            updated = container.repositories.content_items.transition(
                content_item_id,
                ContentItemStage.READY_TO_PUBLISH,
                reason="operator marked ready to publish",
            )
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2
    except Exception as exc:
        print(f"Mark-ready error: {exc}", flush=True)
        return 1
    print("=" * 50)
    print("CONTENT ITEM READY TO PUBLISH")
    print("=" * 50)
    print(f"Content Item: {updated.id}")
    print(f"Title: {updated.title}")
    print(f"Stage: {updated.stage.value}")
    print("=" * 50)
    return 0


def run_linkedin_login(config_path: Path | None = None) -> int:
    try:
        container = initialize_application(config_path=config_path)
        LinkedInPublisher().open_login_session(
            session_dir=container.settings.publishing.linkedin_session_dir,
            timeout_seconds=container.settings.publishing.timeout_seconds,
        )
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2
    except Exception as exc:
        print(f"LinkedIn login session error: {exc}", flush=True)
        return 1
    print("LinkedIn session saved.", flush=True)
    return 0


def run_autopost(
    config_path: Path | None = None,
    *,
    delay_seconds: float | None = None,
    max_posts: int | None = None,
    max_consecutive_failures: int | None = None,
) -> int:
    try:
        container = initialize_application(config_path=config_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2

    report = run_diagnostics(container)
    if not report.ok:
        print_startup_summary(container, report)
        container.logger.error("autopost_startup_diagnostics_failed", extra={"component": "autopost"})
        return 1

    runner = AutopostRunner(
        container,
        delay_seconds=default_delay_seconds() if delay_seconds is None else delay_seconds,
        max_posts=max_posts,
        max_consecutive_failures=(
            default_max_consecutive_failures() if max_consecutive_failures is None else max_consecutive_failures
        ),
    )
    result = runner.run_forever()
    print("=" * 72)
    print("AUTOPOST STOPPED")
    print("=" * 72)
    print(f"Published: {result.published}")
    print(f"Attempts: {result.attempts}")
    print(f"Reason: {result.stopped_reason}")
    print("=" * 72)
    return 0 if result.published > 0 or result.stopped_reason in {"max posts reached", "operator stop requested"} else 1


def _latest_image_ready_content_item_id(container: ServiceContainer) -> str | None:
    with container.repositories.content_items.database.connect() as connection:
        row = connection.execute(
            """
            SELECT id
            FROM content_items
            WHERE stage = ? AND status = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (ContentItemStage.IMAGE_READY.value, "active"),
        ).fetchone()
    return None if row is None else str(row["id"])


def run_app(config_path: Path | None = None) -> int:
    try:
        container = initialize_application(config_path=config_path)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", flush=True)
        return 2

    report = run_diagnostics(container)
    print_startup_summary(container, report)
    if not report.ok:
        container.logger.error("startup_diagnostics_failed", extra={"component": "health"})
        return 1

    stop_requested = False

    def request_stop(signum: int, _frame: object) -> None:
        nonlocal stop_requested
        stop_requested = True
        container.logger.info("shutdown_requested", extra={"component": "runtime", "signal": signum})

    previous_sigint = signal.signal(signal.SIGINT, request_stop)
    previous_sigterm = signal.signal(signal.SIGTERM, request_stop)
    container.scheduler.start()
    container.logger.info("runtime_idle", extra={"component": "runtime"})
    try:
        while not stop_requested:
            time.sleep(container.settings.app.idle_interval_seconds)
    finally:
        container.scheduler.stop(wait=True)
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)
        container.logger.info("runtime_stopped", extra={"component": "runtime"})
    return 0
