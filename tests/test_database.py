from __future__ import annotations

from pathlib import Path

from content_engine.db import Database, MigrationRunner, RepositoryRegistry


def test_database_initialization_applies_schema(tmp_path: Path) -> None:
    database = Database(tmp_path / "storage/test.sqlite3")
    migrations = MigrationRunner(database)

    applied = migrations.apply()
    repositories = RepositoryRegistry.create(database)

    assert applied == [
        "001_initial_schema",
        "002_job_orchestration",
        "003_topic_discovery",
        "004_content_planning",
        "005_knowledge_engine",
        "006_content_lifecycle",
        "007_writing_engine",
        "008_image_generation",
        "009_content_intelligence",
        "010_linkedin_publisher",
    ]
    assert repositories.health.database_ok() is True
    assert repositories.health.table_exists("topics") is True
    assert repositories.health.table_exists("jobs") is True
    assert repositories.health.table_exists("audit_log") is True
    assert repositories.health.table_exists("content_items") is True
    assert repositories.health.table_exists("content_item_artifacts") is True
    assert repositories.health.table_exists("content_item_stage_history") is True
    assert repositories.health.table_exists("post_artifacts") is True
    assert repositories.health.table_exists("image_prompts") is True
    assert repositories.health.table_exists("image_artifacts") is True
    assert repositories.health.table_exists("experiments") is True
    assert repositories.health.table_exists("artifact_lineage") is True
    assert repositories.health.table_exists("content_metrics") is True
    assert repositories.health.table_exists("content_scores") is True
    assert repositories.health.table_exists("publication_artifacts") is True


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "test.sqlite3")
    migrations = MigrationRunner(database)

    assert migrations.apply() == [
        "001_initial_schema",
        "002_job_orchestration",
        "003_topic_discovery",
        "004_content_planning",
        "005_knowledge_engine",
        "006_content_lifecycle",
        "007_writing_engine",
        "008_image_generation",
        "009_content_intelligence",
        "010_linkedin_publisher",
    ]
    assert migrations.apply() == []
    assert migrations.current_versions() == [
        "001_initial_schema",
        "002_job_orchestration",
        "003_topic_discovery",
        "004_content_planning",
        "005_knowledge_engine",
        "006_content_lifecycle",
        "007_writing_engine",
        "008_image_generation",
        "009_content_intelligence",
        "010_linkedin_publisher",
    ]
