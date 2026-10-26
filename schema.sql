-- Internship Board schema (SQLite)
CREATE TABLE IF NOT EXISTS internships (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  title            TEXT    NOT NULL CHECK (length(title) BETWEEN 3 AND 120),
  company          TEXT    NOT NULL CHECK (length(company) BETWEEN 2 AND 80),
  location         TEXT    NOT NULL,
  work_mode        TEXT    NOT NULL CHECK (work_mode IN ('remote','hybrid','onsite')),
  stipend_monthly  INTEGER CHECK (stipend_monthly IS NULL OR stipend_monthly >= 0),
  duration_weeks   INTEGER NOT NULL CHECK (duration_weeks BETWEEN 1 AND 52),
  status           TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('draft','open','closed')),
  apply_url        TEXT,
  description      TEXT    NOT NULL DEFAULT '',
  created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE (title, company)
);
CREATE INDEX IF NOT EXISTS idx_internships_status ON internships(status);
