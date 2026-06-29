CREATE TABLE IF NOT EXISTS validation_sessions (
  id            TEXT PRIMARY KEY,
  session_hash  TEXT NOT NULL,          -- anonymized: SHA256(session_id)
  niche_slug    TEXT NOT NULL,          -- normalized niche label
  pricing_model TEXT NOT NULL,          -- usage | flat | freemium
  outcome       TEXT,                   -- PASSED | KILLED | PENDING
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saturation_signals (
  id              TEXT PRIMARY KEY,
  session_hash    TEXT NOT NULL,
  niche_slug      TEXT NOT NULL,
  saturation_score NUMERIC(4,2),        -- 0.00–10.00
  competitor_count INTEGER,
  sentiment_delta  NUMERIC(5,4),        -- normalized -1 to +1
  sources_cited    INTEGER,
  created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cac_ltv_benchmarks (
  id             TEXT PRIMARY KEY,
  session_hash   TEXT NOT NULL,
  niche_slug     TEXT NOT NULL,
  pricing_model  TEXT NOT NULL,
  estimated_cac  NUMERIC(10,2),
  estimated_ltv  NUMERIC(10,2),
  viability_ratio NUMERIC(6,4),         -- LTV/CAC
  created_at     TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS failure_taxonomy (
  id            TEXT PRIMARY KEY,
  session_hash  TEXT NOT NULL,
  niche_slug    TEXT NOT NULL,
  kill_reason   TEXT NOT NULL,          -- SATURATION | UNIT_ECON | NO_DIFFERENTIATOR | CITATION_FAIL
  saturation_score NUMERIC(4,2),
  retry_count   INTEGER DEFAULT 0,
  created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
