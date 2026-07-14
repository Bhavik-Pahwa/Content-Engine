ALTER TABLE topics ADD COLUMN url TEXT;

ALTER TABLE topics ADD COLUMN author TEXT;

ALTER TABLE topics ADD COLUMN score INTEGER;

ALTER TABLE topics ADD COLUMN published_at TEXT;

ALTER TABLE topics ADD COLUMN provider_name TEXT;

ALTER TABLE topics ADD COLUMN normalized_url TEXT;

ALTER TABLE topics ADD COLUMN normalized_title TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_topics_normalized_url_unique
ON topics(normalized_url)
WHERE normalized_url IS NOT NULL AND normalized_url != '';

CREATE INDEX IF NOT EXISTS idx_topics_normalized_title
ON topics(normalized_title);

CREATE INDEX IF NOT EXISTS idx_topics_provider_name
ON topics(provider_name);
