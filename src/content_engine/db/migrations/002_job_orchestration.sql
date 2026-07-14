ALTER TABLE jobs ADD COLUMN dependencies_json TEXT NOT NULL DEFAULT '[]';

ALTER TABLE jobs ADD COLUMN started_at TEXT;

ALTER TABLE jobs ADD COLUMN completed_at TEXT;

CREATE INDEX IF NOT EXISTS idx_jobs_status_priority_created
ON jobs(status, priority, created_at);

CREATE INDEX IF NOT EXISTS idx_jobs_locked_at
ON jobs(locked_at);
