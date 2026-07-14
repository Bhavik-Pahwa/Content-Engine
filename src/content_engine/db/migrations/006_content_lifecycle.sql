CREATE TABLE IF NOT EXISTS content_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    source_topic_id TEXT REFERENCES topics(id) ON DELETE SET NULL,
    failure_reason TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_content_items_source_topic_id_unique
ON content_items(source_topic_id)
WHERE source_topic_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_content_items_stage
ON content_items(stage);

CREATE INDEX IF NOT EXISTS idx_content_items_status
ON content_items(status);

CREATE TABLE IF NOT EXISTS content_item_artifacts (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'primary',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_item_id, artifact_type, artifact_id, role)
);

CREATE INDEX IF NOT EXISTS idx_content_item_artifacts_item
ON content_item_artifacts(content_item_id);

CREATE INDEX IF NOT EXISTS idx_content_item_artifacts_lookup
ON content_item_artifacts(artifact_type, artifact_id);

CREATE TABLE IF NOT EXISTS content_item_stage_history (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    reason TEXT,
    job_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_content_item_stage_history_item
ON content_item_stage_history(content_item_id, created_at);
