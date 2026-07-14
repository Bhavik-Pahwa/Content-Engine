ALTER TABLE image_artifacts ADD COLUMN version_number INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    knowledge_document_id TEXT REFERENCES knowledge_documents(id) ON DELETE SET NULL,
    content_plan_id TEXT REFERENCES content_plans(id) ON DELETE SET NULL,
    post_artifact_id TEXT REFERENCES post_artifacts(id) ON DELETE SET NULL,
    image_artifact_id TEXT REFERENCES image_artifacts(id) ON DELETE SET NULL,
    prompt_version TEXT,
    system_prompt_version TEXT,
    user_prompt_version TEXT,
    image_prompt_version TEXT,
    llm_provider TEXT,
    llm_model TEXT,
    temperature REAL,
    top_p REAL,
    image_provider TEXT,
    image_model TEXT,
    persona TEXT,
    hook TEXT,
    visual_theme TEXT,
    generation_timestamp TEXT NOT NULL,
    configuration_snapshot_json TEXT NOT NULL DEFAULT '{}',
    git_commit_hash TEXT,
    notes TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_experiments_content_item
ON experiments(content_item_id, created_at);

CREATE INDEX IF NOT EXISTS idx_experiments_post
ON experiments(post_artifact_id);

CREATE TABLE IF NOT EXISTS artifact_lineage (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    parent_artifact_type TEXT NOT NULL,
    parent_artifact_id TEXT NOT NULL,
    child_artifact_type TEXT NOT NULL,
    child_artifact_id TEXT NOT NULL,
    relationship TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_item_id, parent_artifact_type, parent_artifact_id, child_artifact_type, child_artifact_id, relationship)
);

CREATE INDEX IF NOT EXISTS idx_artifact_lineage_content_item
ON artifact_lineage(content_item_id, created_at);

CREATE TABLE IF NOT EXISTS content_metrics (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    post_artifact_id TEXT REFERENCES post_artifacts(id) ON DELETE SET NULL,
    image_artifact_id TEXT REFERENCES image_artifacts(id) ON DELETE SET NULL,
    publishing_timestamp TEXT,
    collection_timestamp TEXT,
    impressions INTEGER,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    shares INTEGER,
    bookmarks INTEGER,
    click_through_rate REAL,
    engagement_rate REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_item_id, platform, post_artifact_id, image_artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_content_metrics_content_item
ON content_metrics(content_item_id, platform);

CREATE TABLE IF NOT EXISTS content_scores (
    id TEXT PRIMARY KEY,
    content_item_id TEXT NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    score REAL NOT NULL,
    reading_level REAL NOT NULL,
    length_score REAL NOT NULL,
    hook_quality REAL NOT NULL,
    paragraph_count INTEGER NOT NULL,
    hashtag_count INTEGER NOT NULL,
    duplicate_score REAL NOT NULL,
    prompt_confidence REAL NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(content_item_id, artifact_type, artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_content_scores_content_item
ON content_scores(content_item_id, created_at);
