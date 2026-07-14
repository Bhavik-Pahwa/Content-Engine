"""CLI reporting for content intelligence."""

from __future__ import annotations

from dataclasses import dataclass

from content_engine.domain import ArtifactType
from content_engine.services import ServiceContainer


@dataclass(frozen=True)
class ReportResult:
    lines: tuple[str, ...]

    def print(self) -> None:
        print("\n".join(self.lines), flush=True)


def build_report(
    container: ServiceContainer,
    *,
    command: str,
    identifier: str | None = None,
    limit: int = 20,
) -> ReportResult:
    if command == "list-assets":
        return ReportResult(tuple(_list_assets(container, limit=limit)))
    if command == "show-latest-asset":
        return ReportResult(tuple(_show_latest_asset(container)))
    if command == "show-experiment":
        return ReportResult(tuple(_show_experiment(container, identifier=identifier)))
    if command == "show-pipeline":
        return ReportResult(tuple(_show_pipeline(container, identifier=identifier)))
    if command == "show-statistics":
        return ReportResult(tuple(_show_statistics(container)))
    raise ValueError(f"Unknown report command: {command}")


def _list_assets(container: ServiceContainer, *, limit: int) -> list[str]:
    rows = _content_item_rows(container, limit=limit)
    lines = ["Content Assets", "=" * 50]
    if not rows:
        return [*lines, "No content assets found."]
    for row in rows:
        experiment = container.repositories.intelligence.latest_experiment_for_content_item(str(row["id"]))
        score = _latest_score(container, str(row["id"]))
        lines.extend(
            [
                f"{row['id']}",
                f"  title: {row['title']}",
                f"  stage: {row['stage']} | status: {row['status']}",
                f"  experiment: {experiment.id if experiment else 'none'}",
                f"  score: {score.score:.2f}" if score else "  score: none",
            ]
        )
    return lines


def _show_latest_asset(container: ServiceContainer) -> list[str]:
    row = _latest_content_item_row(container)
    if row is None:
        return ["Latest Asset", "=" * 50, "No content assets found."]
    content_item_id = str(row["id"])
    artifacts = container.repositories.content_items.artifacts_for_item(content_item_id)
    experiment = container.repositories.intelligence.latest_experiment_for_content_item(content_item_id)
    score = _latest_score(container, content_item_id)
    lines = [
        "Latest Asset",
        "=" * 50,
        f"ID: {content_item_id}",
        f"Title: {row['title']}",
        f"Stage: {row['stage']}",
        f"Status: {row['status']}",
        "",
        "Artifacts",
    ]
    for artifact in artifacts:
        lines.append(f"- {artifact.artifact_type.value}: {artifact.artifact_id}")
    lines.extend(
        [
            "",
            f"Experiment: {experiment.id if experiment else 'none'}",
            f"Score: {score.score:.2f}" if score else "Score: none",
        ]
    )
    return lines


def _show_experiment(container: ServiceContainer, *, identifier: str | None) -> list[str]:
    experiment = (
        container.repositories.intelligence.get_experiment(identifier)
        if identifier
        else container.repositories.intelligence.latest_experiment()
    )
    if experiment is None:
        return ["Experiment", "=" * 50, "No experiment found."]
    lines = [
        "Experiment",
        "=" * 50,
        f"ID: {experiment.id}",
        f"Content Item: {experiment.content_item_id}",
        f"Persona: {experiment.persona or 'unknown'}",
        f"Hook: {experiment.hook or 'unknown'}",
        f"Visual Theme: {experiment.visual_theme or 'unknown'}",
        f"Prompt Version: {experiment.prompt_version or 'unknown'}",
        f"LLM: {experiment.llm_provider or 'unknown'} / {experiment.llm_model or 'unknown'}",
        f"Image: {experiment.image_provider or 'unknown'} / {experiment.image_model or 'unknown'}",
        f"Generated: {experiment.generation_timestamp.isoformat()}",
        f"Git Commit: {experiment.git_commit_hash or 'unavailable'}",
        "",
        "Artifact IDs",
        f"- knowledge: {experiment.metadata.get('knowledge_document_id')}",
        f"- plan: {experiment.metadata.get('content_plan_id')}",
        f"- post: {experiment.metadata.get('post_artifact_id')}",
        f"- image: {experiment.metadata.get('image_artifact_id')}",
        "",
        "Generation Metadata",
        f"- writing attempts: {experiment.metadata.get('writing_attempts')}",
        f"- writing duration seconds: {experiment.metadata.get('writing_duration_seconds')}",
        f"- image duration seconds: {experiment.metadata.get('image_generation_duration_seconds')}",
        f"- content score: {experiment.metadata.get('content_score')}",
    ]
    return lines


def _show_pipeline(container: ServiceContainer, *, identifier: str | None) -> list[str]:
    row = _content_item_row(container, identifier) if identifier else _latest_content_item_row(container)
    if row is None:
        return ["Pipeline", "=" * 50, "No content item found."]
    content_item_id = str(row["id"])
    lines = ["Pipeline", "=" * 50, f"Content Item: {content_item_id}", f"Title: {row['title']}", ""]
    lines.append("Stage History")
    for transition in container.repositories.content_items.stage_history(content_item_id):
        from_stage = transition.from_stage.value if transition.from_stage else "start"
        lines.append(f"- {from_stage} -> {transition.to_stage.value}: {transition.reason or ''}")
    lines.append("")
    lines.append("Lineage")
    lineage = container.repositories.intelligence.lineage_for_content_item(content_item_id)
    if not lineage:
        lines.append("- no lineage recorded")
    for edge in lineage:
        lines.append(
            f"- {edge.parent_artifact_type.value}:{edge.parent_artifact_id} -> "
            f"{edge.child_artifact_type.value}:{edge.child_artifact_id} ({edge.relationship})"
        )
    return lines


def _show_statistics(container: ServiceContainer) -> list[str]:
    lifecycle = container.repositories.content_items.stats()
    posts = container.repositories.posts.stats()
    images = container.repositories.images.stats()
    intelligence = container.repositories.intelligence.stats()
    publications = container.repositories.publications.stats()
    lines = [
        "Statistics",
        "=" * 50,
        f"Content items: {lifecycle.items_created}",
        f"Failed items: {lifecycle.failed_items}",
        f"Posts: {posts.total}",
        f"Images: {images.total}",
        f"Publication attempts: {publications.total}",
        f"Published: {publications.published}",
        f"Publish failures: {publications.failed}",
        f"Publish dry-runs/skips: {publications.skipped}",
        f"Experiments: {intelligence.experiments}",
        f"Lineage edges: {intelligence.lineage_edges}",
        f"Metrics placeholders: {intelligence.metrics_placeholders}",
        f"Scored artifacts: {intelligence.scored_artifacts}",
        f"Average content score: {intelligence.average_score:.2f}",
        "",
        "Stage Distribution",
    ]
    for stage, count in sorted(lifecycle.stage_distribution.items()):
        lines.append(f"- {stage}: {count}")
    return lines


def _content_item_rows(container: ServiceContainer, *, limit: int):
    with container.repositories.content_items.database.connect() as connection:
        return connection.execute(
            "SELECT * FROM content_items ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def _latest_content_item_row(container: ServiceContainer):
    with container.repositories.content_items.database.connect() as connection:
        return connection.execute("SELECT * FROM content_items ORDER BY updated_at DESC LIMIT 1").fetchone()


def _content_item_row(container: ServiceContainer, identifier: str | None):
    if identifier is None:
        return None
    with container.repositories.content_items.database.connect() as connection:
        return connection.execute("SELECT * FROM content_items WHERE id = ?", (identifier,)).fetchone()


def _latest_score(container: ServiceContainer, content_item_id: str):
    scores = container.repositories.intelligence.scores_for_content_item(content_item_id)
    if scores:
        return scores[-1]
    post_artifact = _latest_artifact(container, content_item_id, ArtifactType.POST)
    if post_artifact is None:
        return None
    return container.repositories.intelligence.score_for_artifact(
        content_item_id=content_item_id,
        artifact_type=ArtifactType.POST,
        artifact_id=post_artifact.artifact_id,
    )


def _latest_artifact(container: ServiceContainer, content_item_id: str, artifact_type: ArtifactType):
    artifacts = [
        artifact
        for artifact in container.repositories.content_items.artifacts_for_item(content_item_id)
        if artifact.artifact_type == artifact_type
    ]
    return artifacts[-1] if artifacts else None
