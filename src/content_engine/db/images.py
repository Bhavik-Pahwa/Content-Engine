"""Image prompt and artifact persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from sqlite3 import Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import ImageArtifact, ImageArtifactStatus, ImagePrompt, Platform


@dataclass(frozen=True)
class ImageArtifactStats:
    total: int
    created: int
    failed: int
    average_generation_seconds: float
    average_file_bytes: float


class ImageRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_prompt(
        self,
        *,
        content_item_id: str,
        platform: Platform,
        positive_prompt: str,
        negative_prompt: str | None,
        style_metadata: dict[str, Any],
        prompt_version: str,
        prompt_hash: str,
    ) -> ImagePrompt:
        prompt_id = str(uuid.uuid4())
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO image_prompts (
                    id, content_item_id, platform, positive_prompt,
                    negative_prompt, style_metadata_json, prompt_version,
                    prompt_hash, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    prompt_id,
                    content_item_id,
                    platform.value,
                    positive_prompt,
                    negative_prompt,
                    json.dumps(style_metadata, sort_keys=True),
                    prompt_version,
                    prompt_hash,
                    _format_datetime(now),
                ),
            )
        return self.required_prompt(prompt_id)

    def get_prompt(self, prompt_id: str) -> ImagePrompt | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM image_prompts WHERE id = ?", (prompt_id,)).fetchone()
        return _row_to_prompt(row) if row else None

    def required_prompt(self, prompt_id: str) -> ImagePrompt:
        prompt = self.get_prompt(prompt_id)
        if prompt is None:
            raise LookupError(f"Image prompt not found: {prompt_id}")
        return prompt

    def create_artifact(
        self,
        *,
        content_item_id: str,
        prompt_id: str,
        platform: Platform,
        provider: str,
        model: str,
        positive_prompt: str,
        negative_prompt: str | None,
        seed: int,
        width: int,
        height: int,
        generation_time_seconds: float,
        file_path: Path,
        file_hash: str,
        metadata: dict[str, Any],
        status: ImageArtifactStatus = ImageArtifactStatus.CREATED,
    ) -> ImageArtifact:
        artifact_id = str(uuid.uuid4())
        now = _now()
        version_number = self.next_version_number(content_item_id, platform)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO image_artifacts (
                    id, content_item_id, prompt_id, platform, version_number, provider, model,
                    positive_prompt, negative_prompt, seed, width, height,
                    generation_time_seconds, file_path, file_hash, status,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    content_item_id,
                    prompt_id,
                    platform.value,
                    version_number,
                    provider,
                    model,
                    positive_prompt,
                    negative_prompt,
                    seed,
                    width,
                    height,
                    generation_time_seconds,
                    str(file_path),
                    file_hash,
                    status.value,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    _format_datetime(now),
                ),
            )
        return self.required_artifact(artifact_id)

    def get_artifact(self, artifact_id: str) -> ImageArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM image_artifacts WHERE id = ?", (artifact_id,)).fetchone()
        return _row_to_artifact(row) if row else None

    def next_version_number(self, content_item_id: str, platform: Platform) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
                FROM image_artifacts
                WHERE content_item_id = ? AND platform = ?
                """,
                (content_item_id, platform.value),
            ).fetchone()
        return int(row["next_version"])

    def required_artifact(self, artifact_id: str) -> ImageArtifact:
        artifact = self.get_artifact(artifact_id)
        if artifact is None:
            raise LookupError(f"Image artifact not found: {artifact_id}")
        return artifact

    def latest_for_content_item(self, content_item_id: str, platform: Platform) -> ImageArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM image_artifacts
                WHERE content_item_id = ? AND platform = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (content_item_id, platform.value),
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def find_cached_artifact(
        self,
        *,
        prompt_hash: str,
        provider: str,
        model: str,
        width: int,
        height: int,
    ) -> ImageArtifact | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT image_artifacts.*
                FROM image_artifacts
                JOIN image_prompts ON image_artifacts.prompt_id = image_prompts.id
                WHERE image_prompts.prompt_hash = ?
                  AND image_artifacts.provider = ?
                  AND image_artifacts.model = ?
                  AND image_artifacts.width = ?
                  AND image_artifacts.height = ?
                  AND image_artifacts.status = ?
                ORDER BY image_artifacts.created_at DESC
                LIMIT 1
                """,
                (prompt_hash, provider, model, width, height, ImageArtifactStatus.CREATED.value),
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def has_valid_hash(self, file_hash: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM image_artifacts
                WHERE file_hash = ? AND status = ?
                """,
                (file_hash, ImageArtifactStatus.CREATED.value),
            ).fetchone()
        return int(row["count"]) > 0

    def stats(self) -> ImageArtifactStats:
        with self.database.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) AS count FROM image_artifacts").fetchone()["count"])
            created = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM image_artifacts WHERE status = ?",
                    (ImageArtifactStatus.CREATED.value,),
                ).fetchone()["count"]
            )
            failed = int(
                connection.execute(
                    "SELECT COUNT(*) AS count FROM image_artifacts WHERE status = ?",
                    (ImageArtifactStatus.FAILED.value,),
                ).fetchone()["count"]
            )
            rows = connection.execute(
                "SELECT generation_time_seconds, metadata_json FROM image_artifacts WHERE status = ?",
                (ImageArtifactStatus.CREATED.value,),
            ).fetchall()
        durations = [float(row["generation_time_seconds"]) for row in rows]
        sizes = [int(json.loads(str(row["metadata_json"] or "{}")).get("file_size_bytes", 0)) for row in rows]
        return ImageArtifactStats(
            total=total,
            created=created,
            failed=failed,
            average_generation_seconds=sum(durations) / len(durations) if durations else 0.0,
            average_file_bytes=sum(sizes) / len(sizes) if sizes else 0.0,
        )


def _row_to_prompt(row: Row) -> ImagePrompt:
    return ImagePrompt(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        platform=Platform(str(row["platform"])),
        positive_prompt=str(row["positive_prompt"]),
        negative_prompt=None if row["negative_prompt"] is None else str(row["negative_prompt"]),
        style_metadata=json.loads(str(row["style_metadata_json"] or "{}")),
        prompt_version=str(row["prompt_version"]),
        prompt_hash=str(row["prompt_hash"]),
        created_at=_parse_datetime(row["created_at"]) or _now(),
    )


def _row_to_artifact(row: Row) -> ImageArtifact:
    return ImageArtifact(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        prompt_id=str(row["prompt_id"]),
        platform=Platform(str(row["platform"])),
        version_number=int(row["version_number"]),
        provider=str(row["provider"]),
        model=str(row["model"]),
        positive_prompt=str(row["positive_prompt"]),
        negative_prompt=None if row["negative_prompt"] is None else str(row["negative_prompt"]),
        seed=int(row["seed"]),
        width=int(row["width"]),
        height=int(row["height"]),
        generation_time_seconds=float(row["generation_time_seconds"]),
        file_path=Path(str(row["file_path"])),
        file_hash=str(row["file_hash"]),
        status=ImageArtifactStatus(str(row["status"])),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=_parse_datetime(row["created_at"]) or _now(),
        updated_at=_parse_datetime(row["updated_at"]) or _now(),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
