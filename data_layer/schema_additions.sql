CREATE TABLE IF NOT EXISTS roadmap_sessions (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES validation_sessions(id),
  user_id TEXT,
  thesis_summary TEXT NOT NULL,
  total_days INTEGER NOT NULL DEFAULT 90,
  started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  current_day INTEGER DEFAULT 1,
  completion_pct REAL DEFAULT 0,
  last_checkin_at DATETIME,
  status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS roadmap_tasks (
  id TEXT PRIMARY KEY,
  roadmap_session_id TEXT NOT NULL REFERENCES roadmap_sessions(id),
  day_number INTEGER NOT NULL,
  week_number INTEGER NOT NULL,
  task_title TEXT NOT NULL,
  task_description TEXT,
  owner TEXT,
  deliverable TEXT,
  status TEXT DEFAULT 'pending',
  completed_at DATETIME,
  UNIQUE(roadmap_session_id, day_number)
);
CREATE INDEX IF NOT EXISTS idx_roadmap_tasks_session ON roadmap_tasks(roadmap_session_id);
