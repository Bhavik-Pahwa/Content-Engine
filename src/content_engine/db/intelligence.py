"""Content intelligence persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from sqlite3 import IntegrityError, Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import ArtifactLineage, ArtifactType, ContentMetrics, ContentScore, Experiment, Platform


@dataclass(frozen=True)
class ContentIntelligenceStats:
    experiments: int
    lineage_edges: int
    metrics_placeholders: int
    scored_artifacts: int
    average_score: float


class ContentIntelligenceRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_experiment(
        self,
        *,
        content_item_id: str,
        knowledge_document_id: str | None,
        content_plan_id: str | None,
        post_artifact_id: str | None,
        image_artifact_id: str | None,
        prompt_version: str | None,
        system_prompt_version: str | None,
        user_prompt_version: str | None,
        image_prompt_version: str | None,
        llm_provider: str | None,
        llm_model: str | None,
        temperature: float | None,
        top_p: float | None,
        image_provider: str | None,
        image_model: str | None,
        persona: str | None,
        hook: str | None,
        visual_theme: str | None,
        generation_timestamp: datetime,
        configuration_snapshot: dict[str, Any],
        git_commit_hash: str | None,
        notes: str | None,
        metadata: dict[str, Any],
    ) -> Experiment:
        experiment_id = str(uuid.uuid4())
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO experiments (
                    id, content_item_id, knowledge_document_id, content_plan_id,
                    post_artifact_id, image_artifact_id, prompt_version,
                    system_prompt_version, user_prompt_version, image_prompt_version,
                    llm_provider, llm_model, temperature, top_p,
                    image_provider, image_model, persona, hook, visual_theme,
                    generation_timestamp, configuration_snapshot_json,
                    git_commit_hash, notes, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment_id,
                    content_item_id,
                    knowledge_document_id,
                    content_plan_id,
                    post_artifact_id,
                    image_artifact_id,
                    prompt_version,
                    system_prompt_version,
                    user_prompt_version,
                    image_prompt_version,
                    llm_provider,
                    llm_model,
                    temperature,
                    top_p,
                    image_provider,
                    image_model,
                    persona,
                    hook,
                    visual_theme,
                    _format_datetime(generation_timestamp),
                    json.dumps(configuration_snapshot, sort_keys=True),
                    git_commit_hash,
                    notes,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                ),
            )
        return self.required_experiment(experiment_id)

    def get_experiment(self, experiment_id: str) -> Experiment | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
        return _row_to_experiment(row) if row else None

    def required_experiment(self, experiment_id: str) -> Experiment:
        experiment = self.get_experiment(experiment_id)
        if experiment is None:
            raise LookupError(f"Experiment not found: {experiment_id}")
        return experiment

    def latest_experiment_for_content_item(self, content_item_id: str) -> Experiment | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM experiments
                WHERE content_item_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (content_item_id,),
            ).fetchone()
        return _row_to_experiment(row) if row else None

    def experiment_for_artifacts(
        self,
        *,
        content_item_id: str,
        post_artifact_id: str | None,
        image_artifact_id: str | None,
    ) -> Experiment | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM experiments
                WHERE content_item_id = ?
                  AND post_artifact_id IS ?
                  AND image_artifact_id IS ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (content_item_id, post_artifact_id, image_artifact_id),
            ).fetchone()
        return _row_to_experiment(row) if row else None

    def latest_experiment(self) -> Experiment | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM experiments ORDER BY created_at DESC LIMIT 1").fetchone()
        return _row_to_experiment(row) if row else None

    def list_experiments(self, *, limit: int = 20) -> list[Experiment]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_experiment(row) for row in rows]

    def add_lineage(
        self,
        *,
        content_item_id: str,
        parent_artifact_type: ArtifactType,
        parent_artifact_id: str,
        child_artifact_type: ArtifactType,
        child_artifact_id: str,
        relationship: str,
    ) -> ArtifactLineage:
        edge_id = str(uuid.uuid4())
        now = _now()
        try:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO artifact_lineage (
                        id, content_item_id, parent_artifact_type, parent_artifact_id,
                        child_artifact_type, child_artifact_id, relationship, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        content_item_id,
                        parent_artifact_type.value,
                        parent_artifact_id,
                        child_artifact_type.value,
                        child_artifact_id,
                        relationship,
                        _format_datetime(now),
                    ),
                )
        except IntegrityError:
            existing = self.find_lineage(
                content_item_id=content_item_id,
                parent_artifact_type=parent_artifact_type,
                parent_artifact_id=parent_artifact_id,
                child_artifact_type=child_artifact_type,
                child_artifact_id=child_artifact_id,
                relationship=relationship,
            )
            if existing is not None:
                return existing
            raise
        return self.required_lineage(edge_id)

    def find_lineage(
        self,
        *,
        content_item_id: str,
        parent_artifact_type: ArtifactType,
        parent_artifact_id: str,
        child_artifact_type: ArtifactType,
        child_artifact_id: str,
        relationship: str,
    ) -> ArtifactLineage | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM artifact_lineage
                WHERE content_item_id = ?
                  AND parent_artifact_type = ?
                  AND parent_artifact_id = ?
                  AND child_artifact_type = ?
                  AND child_artifact_id = ?
                  AND relationship = ?
                """,
                (
                    content_item_id,
                    parent_artifact_type.value,
                    parent_artifact_id,
                    child_artifact_type.value,
                    child_artifact_id,
                    relationship,
                ),
            ).fetchone()
        return _row_to_lineage(row) if row else None

    def required_lineage(self, lineage_id: str) -> ArtifactLineage:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM artifact_lineage WHERE id = ?", (lineage_id,)).fetchone()
        if row is None:
            raise LookupError(f"Artifact lineage not found: {lineage_id}")
        return _row_to_lineage(row)

    def lineage_for_content_item(self, content_item_id: str) -> list[ArtifactLineage]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artifact_lineage WHERE content_item_id = ? ORDER BY created_at ASC",
                (content_item_id,),
            ).fetchall()
        return [_row_to_lineage(row) for row in rows]

    def create_metrics_placeholder(
        self,
        *,
        content_item_id: str,
        platform: Platform,
        post_artifact_id: str | None,
        image_artifact_id: str | None,
        metadata: dict[str, Any],
    ) -> ContentMetrics:
        existing = self.metrics_for_artifacts(
            content_item_id=content_item_id,
            platform=platform,
            post_artifact_id=post_artifact_id,
            image_artifact_id=image_artifact_id,
        )
        if existing is not None:
            return existing
        metrics_id = str(uuid.uuid4())
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO content_metrics (
                    id, content_item_id, platform, post_artifact_id, image_artifact_id,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metrics_id,
                    content_item_id,
                    platform.value,
                    post_artifact_id,
                    image_artifact_id,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    _format_datetime(now),
                ),
            )
        return self.required_metrics(metrics_id)

    def metrics_for_artifacts(
        self,
        *,
        content_item_id: str,
        platform: Platform,
        post_artifact_id: str | None,
        image_artifact_id: str | None,
    ) -> ContentMetrics | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM content_metrics
                WHERE content_item_id = ?
                  AND platform = ?
                  AND post_artifact_id IS ?
                  AND image_artifact_id IS ?
                """,
                (content_item_id, platform.value, post_artifact_id, image_artifact_id),
            ).fetchone()
        return _row_to_metrics(row) if row else None

    def required_metrics(self, metrics_id: str) -> ContentMetrics:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM content_metrics WHERE id = ?", (metrics_id,)).fetchone()
        if row is None:
            raise LookupError(f"Content metrics not found: {metrics_id}")
        return _row_to_metrics(row)

    def mark_metrics_published(
        self,
        *,
        content_item_id: str,
        platform: Platform,
        post_artifact_id: str | None,
        image_artifact_id: str | None,
        publishing_timestamp: datetime,
    ) -> ContentMetrics | None:
        metrics = self.metrics_for_artifacts(
            content_item_id=content_item_id,
            platform=platform,
            post_artifact_id=post_artifact_id,
            image_artifact_id=image_artifact_id,
        )
        if metrics is None:
            return None
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE content_metrics
                SET publishing_timestamp = ?, updated_at = ?
                WHERE id = ?
                """,
                (_format_datetime(publishing_timestamp), _format_datetime(now), metrics.id),
            )
        return self.required_metrics(metrics.id)

    def create_score(
        self,
        *,
        content_item_id: str,
        artifact_type: ArtifactType,
        artifact_id: str,
        score: float,
        reading_level: float,
        length_score: float,
        hook_quality: float,
        paragraph_count: int,
        hashtag_count: int,
        duplicate_score: float,
        prompt_confidence: float,
        metadata: dict[str, Any],
    ) -> ContentScore:
        existing = self.score_for_artifact(
            content_item_id=content_item_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
        )
        if existing is not None:
            return existing
        score_id = str(uuid.uuid4())
        now = _now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO content_scores (
                    id, content_item_id, artifact_type, artifact_id, score,
                    reading_level, length_score, hook_quality, paragraph_count,
                    hashtag_count, duplicate_score, prompt_confidence,
                    metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    score_id,
                    content_item_id,
                    artifact_type.value,
                    artifact_id,
                    score,
                    reading_level,
                    length_score,
                    hook_quality,
                    paragraph_count,
                    hashtag_count,
                    duplicate_score,
                    prompt_confidence,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                ),
            )
        return self.required_score(score_id)

    def score_for_artifact(
        self,
        *,
        content_item_id: str,
        artifact_type: ArtifactType,
        artifact_id: str,
    ) -> ContentScore | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM content_scores
                WHERE content_item_id = ? AND artifact_type = ? AND artifact_id = ?
                """,
                (content_item_id, artifact_type.value, artifact_id),
            ).fetchone()
        return _row_to_score(row) if row else None

    def required_score(self, score_id: str) -> ContentScore:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM content_scores WHERE id = ?", (score_id,)).fetchone()
        if row is None:
            raise LookupError(f"Content score not found: {score_id}")
        return _row_to_score(row)

    def scores_for_content_item(self, content_item_id: str) -> list[ContentScore]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM content_scores WHERE content_item_id = ? ORDER BY created_at ASC",
                (content_item_id,),
            ).fetchall()
        return [_row_to_score(row) for row in rows]

    def stats(self) -> ContentIntelligenceStats:
        with self.database.connect() as connection:
            experiments = int(connection.execute("SELECT COUNT(*) AS count FROM experiments").fetchone()["count"])
            lineage = int(connection.execute("SELECT COUNT(*) AS count FROM artifact_lineage").fetchone()["count"])
            metrics = int(connection.execute("SELECT COUNT(*) AS count FROM content_metrics").fetchone()["count"])
            scored = int(connection.execute("SELECT COUNT(*) AS count FROM content_scores").fetchone()["count"])
            row = connection.execute("SELECT AVG(score) AS average_score FROM content_scores").fetchone()
        return ContentIntelligenceStats(
            experiments=experiments,
            lineage_edges=lineage,
            metrics_placeholders=metrics,
            scored_artifacts=scored,
            average_score=float(row["average_score"] or 0.0),
        )


def _row_to_experiment(row: Row) -> Experiment:
    return Experiment(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        prompt_version=None if row["prompt_version"] is None else str(row["prompt_version"]),
        llm_provider=None if row["llm_provider"] is None else str(row["llm_provider"]),
        llm_model=None if row["llm_model"] is None else str(row["llm_model"]),
        temperature=None if row["temperature"] is None else float(row["temperature"]),
        top_p=None if row["top_p"] is None else float(row["top_p"]),
        image_provider=None if row["image_provider"] is None else str(row["image_provider"]),
        image_model=None if row["image_model"] is None else str(row["image_model"]),
        persona=None if row["persona"] is None else str(row["persona"]),
        hook=None if row["hook"] is None else str(row["hook"]),
        visual_theme=None if row["visual_theme"] is None else str(row["visual_theme"]),
        generation_timestamp=_parse_datetime(row["generation_timestamp"]) or _now(),
        configuration_snapshot=json.loads(str(row["configuration_snapshot_json"] or "{}")),
        git_commit_hash=None if row["git_commit_hash"] is None else str(row["git_commit_hash"]),
        notes=None if row["notes"] is None else str(row["notes"]),
        metadata={
            **json.loads(str(row["metadata_json"] or "{}")),
            "knowledge_document_id": row["knowledge_document_id"],
            "content_plan_id": row["content_plan_id"],
            "post_artifact_id": row["post_artifact_id"],
            "image_artifact_id": row["image_artifact_id"],
            "system_prompt_version": row["system_prompt_version"],
            "user_prompt_version": row["user_prompt_version"],
            "image_prompt_version": row["image_prompt_version"],
        },
        created_at=_parse_datetime(row["created_at"]) or _now(),
    )


def _row_to_lineage(row: Row) -> ArtifactLineage:
    return ArtifactLineage(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        parent_artifact_type=ArtifactType(str(row["parent_artifact_type"])),
        parent_artifact_id=str(row["parent_artifact_id"]),
        child_artifact_type=ArtifactType(str(row["child_artifact_type"])),
        child_artifact_id=str(row["child_artifact_id"]),
        relationship=str(row["relationship"]),
        created_at=_parse_datetime(row["created_at"]) or _now(),
    )


def _row_to_metrics(row: Row) -> ContentMetrics:
    return ContentMetrics(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        platform=Platform(str(row["platform"])),
        post_artifact_id=None if row["post_artifact_id"] is None else str(row["post_artifact_id"]),
        image_artifact_id=None if row["image_artifact_id"] is None else str(row["image_artifact_id"]),
        publishing_timestamp=_parse_datetime(row["publishing_timestamp"]),
        collection_timestamp=_parse_datetime(row["collection_timestamp"]),
        impressions=_optional_int(row["impressions"]),
        views=_optional_int(row["views"]),
        likes=_optional_int(row["likes"]),
        comments=_optional_int(row["comments"]),
        shares=_optional_int(row["shares"]),
        bookmarks=_optional_int(row["bookmarks"]),
        click_through_rate=_optional_float(row["click_through_rate"]),
        engagement_rate=_optional_float(row["engagement_rate"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=_parse_datetime(row["created_at"]) or _now(),
        updated_at=_parse_datetime(row["updated_at"]) or _now(),
    )


def _row_to_score(row: Row) -> ContentScore:
    return ContentScore(
        id=str(row["id"]),
        content_item_id=str(row["content_item_id"]),
        artifact_type=ArtifactType(str(row["artifact_type"])),
        artifact_id=str(row["artifact_id"]),
        score=float(row["score"]),
        reading_level=float(row["reading_level"]),
        length_score=float(row["length_score"]),
        hook_quality=float(row["hook_quality"]),
        paragraph_count=int(row["paragraph_count"]),
        hashtag_count=int(row["hashtag_count"]),
        duplicate_score=float(row["duplicate_score"]),
        prompt_confidence=float(row["prompt_confidence"]),
        metadata=json.loads(str(row["metadata_json"] or "{}")),
        created_at=_parse_datetime(row["created_at"]) or _now(),
    )


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


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
