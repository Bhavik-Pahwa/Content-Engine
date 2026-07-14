from __future__ import annotations

from pathlib import Path

from content_engine.app.health import run_diagnostics
from content_engine.app.runtime import initialize_application


def test_initialize_application_builds_service_container(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    container = initialize_application()

    assert container.settings.database.path == tmp_path / "storage/content_engine.sqlite3"
    assert container.repositories.health.database_ok() is True
    assert {provider.name for provider in container.providers.health()} == {
        "hacker_news",
        "openrouter",
        "local_template",
        "mock_publisher",
    }
    assert container.job_handlers.registered_types() == (
        "BUILD_KNOWLEDGE",
        "DISCOVER_TOPICS",
        "GENERATE_IMAGE",
        "PLAN_CONTENT",
        "PUBLISH_LINKEDIN",
        "WRITE_LINKEDIN_POST",
    )
    assert container.workers.names() == []


def test_health_diagnostics_pass_after_initialization(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    container = initialize_application()

    report = run_diagnostics(container)

    assert report.ok is True
    assert {item.name for item in report.items} >= {"configuration", "storage", "database", "logging"}
