CREATE TABLE IF NOT EXISTS image_prompts (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    positive_prompt TEXT NOT NULL,
    negative_prompt TEXT,
    style_metadata_json TEXT NOT NULL DEFAULT '{}',
    prompt_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_image_prompts_content_item
ON image_prompts(content_item_id, platform, created_at);

CREATE INDEX IF NOT EXISTS idx_image_prompts_hash
ON image_prompts(prompt_hash);

CREATE TABLE IF NOT EXISTS image_artifacts (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    prompt_id TEXT NOT NULL REFERENCES image_prompts(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    positive_prompt TEXT NOT NULL,
    negative_prompt TEXT,
    seed INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    generation_time_seconds REAL NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_image_artifacts_content_item
ON image_artifacts(content_item_id, platform, created_at);

CREATE INDEX IF NOT EXISTS idx_image_artifacts_prompt
ON image_artifacts(prompt_id);

CREATE INDEX IF NOT EXISTS idx_image_artifacts_cache
ON image_artifacts(provider, model, width, height, file_hash, status);
