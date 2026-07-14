from __future__ import annotations

from pathlib import Path

import pytest

from content_engine.config import ConfigError, load_settings


def test_load_settings_uses_defaults(tmp_path: Path) -> None:
    settings = load_settings(env={}, base_dir=tmp_path)

    assert settings.app.name == "content-engine"
    assert settings.runtime.dry_run is True
    assert settings.database.path == tmp_path / "storage/content_engine.sqlite3"
    assert settings.logging.level == "INFO"
    assert settings.publishing.linkedin_session_dir == tmp_path / "storage/browser/linkedin"
    assert settings.publishing.screenshot_dir == tmp_path / "storage/screenshots"
    assert settings.publishing.linkedin_author_name == "Bhavik Pahwa"
    assert settings.publishing.linkedin_target_page_name == "First Hand Devs | FHD"


def test_load_settings_reads_config_file(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
        [app]
        name = "test-engine"
        idle_interval_seconds = 5

        [database]
        path = "data/test.sqlite3"

        [runtime]
        queue_target_size = 3
        """,
        encoding="utf-8",
    )

    settings = load_settings(config_path=config, env={}, base_dir=tmp_path)

    assert settings.app.name == "test-engine"
    assert settings.app.idle_interval_seconds == 5
    assert settings.database.path == tmp_path / "data/test.sqlite3"
    assert settings.runtime.queue_target_size == 3


def test_environment_overrides_config_file(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
        [logging]
        level = "INFO"
        """,
        encoding="utf-8",
    )

    settings = load_settings(
        config_path=config,
        env={"CONTENT_ENGINE_LOG_LEVEL": "debug"},
        base_dir=tmp_path,
    )

    assert settings.logging.level == "DEBUG"


def test_publishing_page_target_can_be_configured(tmp_path: Path) -> None:
    settings = load_settings(
        env={
            "CONTENT_ENGINE_LINKEDIN_AUTHOR_NAME": "Account Owner",
            "CONTENT_ENGINE_LINKEDIN_TARGET_PAGE_NAME": "Example Page",
        },
        base_dir=tmp_path,
    )

    assert settings.publishing.linkedin_author_name == "Account Owner"
    assert settings.publishing.linkedin_target_page_name == "Example Page"


def test_load_settings_reads_dotenv_when_env_not_injected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        'OPENROUTER_API_KEY="secret-from-dotenv"\nCONTENT_ENGINE_OPENROUTER_MODEL=openrouter/free\n',
        encoding="utf-8",
    )

    settings = load_settings()

    assert settings.writing.openrouter_api_key == "secret-from-dotenv"
    assert settings.writing.openrouter_model == "openrouter/free"


def test_invalid_configuration_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(env={"CONTENT_ENGINE_IDLE_INTERVAL_SECONDS": "0"}, base_dir=tmp_path)
