"""Repository layer entry points."""

from __future__ import annotations

from dataclasses import dataclass

from content_engine.db.content_plans import ContentPlanRepository
from content_engine.db.content_items import ContentItemRepository
from content_engine.db.connection import Database
from content_engine.db.jobs import JobRepository
from content_engine.db.images import ImageRepository
from content_engine.db.intelligence import ContentIntelligenceRepository
from content_engine.db.knowledge import KnowledgeRepository
from content_engine.db.posts import PostArtifactRepository
from content_engine.db.publications import PublicationArtifactRepository
from content_engine.db.topics import TopicRepository


class HealthRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def database_ok(self) -> bool:
        return self.database.ping()

    def table_exists(self, table_name: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
        return row is not None

    def queue_ok(self) -> bool:
        required_tables = ("jobs", "schema_migrations")
        return all(self.table_exists(table_name) for table_name in required_tables)


class SettingsRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, key: str) -> str | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])


@dataclass(frozen=True)
class RepositoryRegistry:
    health: HealthRepository
    settings: SettingsRepository
    jobs: JobRepository
    topics: TopicRepository
    content_plans: ContentPlanRepository
    content_items: ContentItemRepository
    knowledge: KnowledgeRepository
    posts: PostArtifactRepository
    images: ImageRepository
    intelligence: ContentIntelligenceRepository
    publications: PublicationArtifactRepository

    @classmethod
    def create(cls, database: Database) -> "RepositoryRegistry":
        return cls(
            health=HealthRepository(database),
            settings=SettingsRepository(database),
            jobs=JobRepository(database),
            topics=TopicRepository(database),
            content_plans=ContentPlanRepository(database),
            content_items=ContentItemRepository(database),
            knowledge=KnowledgeRepository(database),
            posts=PostArtifactRepository(database),
            images=ImageRepository(database),
            intelligence=ContentIntelligenceRepository(database),
            publications=PublicationArtifactRepository(database),
        )
