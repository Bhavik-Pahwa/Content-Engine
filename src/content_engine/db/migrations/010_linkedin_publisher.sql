CREATE TABLE IF NOT EXISTS publication_artifacts (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    post_artifact_id TEXT NOT NULL REFERENCES post_artifacts(id) ON DELETE CASCADE,
    image_artifact_id TEXT REFERENCES image_artifacts(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    publish_timestamp TEXT,
    playwright_session TEXT,
    url TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    screenshot_before_path TEXT,
    screenshot_after_path TEXT,
    screenshot_error_path TEXT,
    duration_seconds REAL NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_publication_artifacts_content_item
ON publication_artifacts(content_item_id, platform, created_at);

CREATE INDEX IF NOT EXISTS idx_publication_artifacts_status
ON publication_artifacts(platform, status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_publication_artifacts_one_published
ON publication_artifacts(content_item_id, platform)
WHERE status = 'published';
