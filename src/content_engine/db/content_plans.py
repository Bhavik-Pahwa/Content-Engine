"""Content plan persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlite3 import Row
from typing import Any
import json
import uuid

from content_engine.db.connection import Database
from content_engine.domain import ContentPlan, ContentPlanStatus


class ContentPlanRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        topic_id: str,
        primary_angle: str,
        target_audience: str,
        content_goal: str,
        content_type: str,
        hook_style: str,
        writing_persona: str,
        visual_theme: str,
        image_prompt: str,
        video_prompt: str | None,
        key_points: tuple[str, ...],
        call_to_action: str,
        platform_targets: tuple[str, ...],
        metadata: dict[str, Any],
        status: ContentPlanStatus = ContentPlanStatus.PLANNED,
    ) -> ContentPlan:
        now = _now()
        plan_id = str(uuid.uuid4())
        version_number = self.next_version_number(topic_id)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO content_plans (
                    id, topic_id, version_number, primary_angle, target_audience,
                    content_goal, content_type, hook_style, writing_persona,
                    visual_theme, image_prompt, video_prompt, key_points_json,
                    call_to_action, platform_targets_json, status, metadata_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    topic_id,
                    version_number,
                    primary_angle,
                    target_audience,
                    content_goal,
                    content_type,
                    hook_style,
                    writing_persona,
                    visual_theme,
                    image_prompt,
                    video_prompt,
                    json.dumps(list(key_points), sort_keys=True),
                    call_to_action,
                    json.dumps(list(platform_targets), sort_keys=True),
                    status.value,
                    json.dumps(metadata, sort_keys=True),
                    _format_datetime(now),
                    _format_datetime(now),
                ),
            )
        return self.required(plan_id)

    def get(self, plan_id: str) -> ContentPlan | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM content_plans WHERE id = ?", (plan_id,)).fetchone()
        return _row_to_plan(row) if row else None

    def required(self, plan_id: str) -> ContentPlan:
        plan = self.get(plan_id)
        if plan is None:
            raise LookupError(f"Content plan not found: {plan_id}")
        return plan

    def latest_for_topic(self, topic_id: str) -> ContentPlan | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM content_plans
                WHERE topic_id = ?
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (topic_id,),
            ).fetchone()
        return _row_to_plan(row) if row else None

    def list_for_topic(self, topic_id: str) -> list[ContentPlan]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM content_plans WHERE topic_id = ? ORDER BY version_number ASC",
                (topic_id,),
            ).fetchall()
        return [_row_to_plan(row) for row in rows]

    def count(self) -> int:
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM content_plans").fetchone()
        return int(row["count"])

    def next_version_number(self, topic_id: str) -> int:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM content_plans WHERE topic_id = ?",
                (topic_id,),
            ).fetchone()
        return int(row["next_version"])


def _row_to_plan(row: Row) -> ContentPlan:
    return ContentPlan(
        id=str(row["id"]),
        topic_id=str(row["topic_id"]),
        version_number=int(row["version_number"]),
        primary_angle=str(row["primary_angle"]),
        target_audience=str(row["target_audience"]),
        content_goal=str(row["content_goal"]),
        content_type=str(row["content_type"]),
        hook_style=str(row["hook_style"]),
        writing_persona=str(row["writing_persona"]),
        visual_theme=str(row["visual_theme"]),
        image_prompt=str(row["image_prompt"]),
        video_prompt=None if row["video_prompt"] is None else str(row["video_prompt"]),
        key_points=tuple(json.loads(str(row["key_points_json"] or "[]"))),
        call_to_action=str(row["call_to_action"]),
        platform_targets=tuple(json.loads(str(row["platform_targets_json"] or "[]"))),
        status=ContentPlanStatus(str(row["status"])),
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
