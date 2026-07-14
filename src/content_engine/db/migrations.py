"""Simple SQL migration runner."""

from __future__ import annotations

from pathlib import Path
from sqlite3 import Connection

from content_engine.db.connection import Database


class MigrationRunner:
    def __init__(self, database: Database, migrations_dir: Path | None = None) -> None:
        self.database = database
        self.migrations_dir = migrations_dir or Path(__file__).parent / "migrations"

    def apply(self) -> list[str]:
        applied: list[str] = []
        with self.database.connect() as connection:
            self._ensure_schema_table(connection)
            existing = self._applied_versions(connection)
            for migration in self._migration_files():
                version = migration.stem
                if version in existing:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)",
                    (version,),
                )
                applied.append(version)
        return applied

    def current_versions(self) -> list[str]:
        with self.database.connect() as connection:
            self._ensure_schema_table(connection)
            return sorted(self._applied_versions(connection))

    def _migration_files(self) -> list[Path]:
        return sorted(self.migrations_dir.glob("*.sql"))

    @staticmethod
    def _ensure_schema_table(connection: Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    @staticmethod
    def _applied_versions(connection: Connection) -> set[str]:
        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
        return {str(row["version"]) for row in rows}

