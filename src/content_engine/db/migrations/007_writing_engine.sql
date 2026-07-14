CREATE TABLE IF NOT EXISTS post_artifacts (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    hook TEXT NOT NULL,
    body TEXT NOT NULL,
    call_to_action TEXT NOT NULL,
    hashtags_json TEXT NOT NULL DEFAULT '[]',
    estimated_reading_time_seconds INTEGER NOT NULL,
    generation_metadata_json TEXT NOT NULL DEFAULT '{}',
    provider_metadata_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_item_id, platform, version_number)
);

CREATE INDEX IF NOT EXISTS idx_post_artifacts_content_item
ON post_artifacts(content_item_id);

CREATE INDEX IF NOT EXISTS idx_post_artifacts_platform_status
ON post_artifacts(platform, status);
