CREATE TABLE IF NOT EXISTS knowledge_documents (
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    keywords_json TEXT NOT NULL DEFAULT '[]',
    named_entities_json TEXT NOT NULL DEFAULT '[]',
    technology_tags_json TEXT NOT NULL DEFAULT '[]',
    companies_json TEXT NOT NULL DEFAULT '[]',
    people_json TEXT NOT NULL DEFAULT '[]',
    concepts_json TEXT NOT NULL DEFAULT '[]',
    source_url TEXT NOT NULL,
    canonical_url TEXT,
    author TEXT,
    publication_date TEXT,
    word_count INTEGER NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    reading_time_minutes INTEGER NOT NULL,
    reading_difficulty TEXT NOT NULL,
    estimated_audience TEXT NOT NULL,
    technology_category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    raw_html TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(topic_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_topic_id
ON knowledge_documents(topic_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status
ON knowledge_documents(status);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_source_url
ON knowledge_documents(source_url);
