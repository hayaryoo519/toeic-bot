-- migrations_v5.sql
-- Userテーブルに連続正解数(current_combo)と最大連続正解数(max_combo)を追加

ALTER TABLE users ADD COLUMN current_combo INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN max_combo INTEGER DEFAULT 0;
