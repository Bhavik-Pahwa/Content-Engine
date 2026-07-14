CREATE TABLE IF NOT EXISTS content_plans (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    primary_angle TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    content_goal TEXT NOT NULL,
    content_type TEXT NOT NULL,
    hook_style TEXT NOT NULL,
    writing_persona TEXT NOT NULL,
    visual_theme TEXT NOT NULL,
    image_prompt TEXT NOT NULL,
    video_prompt TEXT,
    key_points_json TEXT NOT NULL DEFAULT '[]',
    call_to_action TEXT NOT NULL,
    platform_targets_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'planned',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(topic_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_content_plans_topic_id
ON content_plans(topic_id);

CREATE INDEX IF NOT EXISTS idx_content_plans_status
ON content_plans(status);
