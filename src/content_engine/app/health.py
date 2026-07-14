"""Startup diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from content_engine.observability.logging import expected_log_files
from content_engine.services import ServiceContainer


@dataclass(frozen=True)
class HealthItem:
    name: str
    ok: bool
    message: str


@dataclass(frozen=True)
class HealthReport:
    items: tuple[HealthItem, ...]

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.items)

    def to_lines(self) -> list[str]:
        lines = ["Startup diagnostics:"]
        for item in self.items:
            status = "OK" if item.ok else "FAIL"
            lines.append(f"- {status}: {item.name} - {item.message}")
        return lines


def run_diagnostics(container: ServiceContainer) -> HealthReport:
    settings = container.settings
    queue_stats = container.repositories.jobs.stats()
    scheduler_status = container.scheduler.status()
    items = [
        HealthItem("configuration", True, f"{settings.app.environment}, dry_run={settings.runtime.dry_run}"),
        _check_directories(container.storage_paths.all_directories()),
        HealthItem("database", container.repositories.health.database_ok(), str(settings.database.path)),
        HealthItem(
            "migrations",
            container.repositories.health.table_exists("schema_migrations"),
            ", ".join(container.migrations.current_versions()) or "no migrations applied",
        ),
        _check_log_files(expected_log_files(settings.logging)),
        HealthItem(
            "queue",
            container.repositories.health.queue_ok(),
            (
                f"pending={queue_stats.pending}, retrying={queue_stats.retrying}, "
                f"running={queue_stats.running}, failed={queue_stats.failed}"
            ),
        ),
        HealthItem("scheduler", True, f"state={scheduler_status.state.value}, concurrency={settings.runtime.worker_concurrency}"),
        HealthItem(
            "worker engine",
            True,
            f"handlers={len(scheduler_status.registered_handlers)}, jobs_started={scheduler_status.metrics.jobs_started}",
        ),
        HealthItem("providers", True, f"{len(container.providers.health())} registered"),
        HealthItem("workers", True, f"{len(container.workers.names())} registered"),
    ]
    return HealthReport(items=tuple(items))


def print_startup_summary(container: ServiceContainer, report: HealthReport) -> None:
    settings = container.settings
    lines = [
        f"Content Engine started: {settings.app.name}",
        f"Environment: {settings.app.environment}",
        f"Database: {settings.database.path}",
        f"Storage: {container.storage_paths.root}",
        f"Logs: {settings.logging.directory}",
        f"Dry run: {settings.runtime.dry_run}",
        f"Publishing paused: {settings.runtime.publishing_paused}",
        f"Scheduler concurrency: {settings.runtime.worker_concurrency}",
        *report.to_lines(),
    ]
    print("\n".join(lines), flush=True)


def _check_directories(paths: tuple[Path, ...]) -> HealthItem:
    missing = [str(path) for path in paths if not path.exists() or not path.is_dir()]
    if missing:
        return HealthItem("storage", False, f"missing directories: {', '.join(missing)}")
    return HealthItem("storage", True, f"{len(paths)} directories ready")


def _check_log_files(paths: list[Path]) -> HealthItem:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        return HealthItem("logging", False, f"missing log files: {', '.join(missing)}")
    return HealthItem("logging", True, f"{len(paths)} log files ready")
