-- SQLite migration SQL

-- Add notion_page_id to questions if not exists
-- NOTE: SQLite doesn't support 'IF NOT EXISTS' for ADD COLUMN easily, 
-- but we can use this script to ensure the schema is up to date.

ALTER TABLE questions ADD COLUMN notion_page_id TEXT;
CREATE UNIQUE INDEX idx_questions_notion_page_id ON questions(notion_page_id);

-- Create ai_generation_logs table
CREATE TABLE IF NOT EXISTS ai_generation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt TEXT,
    generated_question TEXT,
    review_result TEXT,
    created_at DATETIME
);

-- Create sync_logs table
CREATE TABLE IF NOT EXISTS sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notion_page_id TEXT,
    result TEXT,
    error_message TEXT,
    synced_at DATETIME
);
