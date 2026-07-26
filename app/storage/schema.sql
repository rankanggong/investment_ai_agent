CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL UNIQUE,
  name TEXT,
  asset_type TEXT,
  sector TEXT,
  industry TEXT,
  country TEXT,
  currency TEXT,
  role TEXT,
  watch_level TEXT,
  source TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  date TEXT NOT NULL,
  open REAL,
  high REAL,
  low REAL,
  close REAL,
  adjusted_close REAL,
  volume REAL,
  source TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(symbol, date, source)
);

CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_type TEXT,
  report_date TEXT,
  title TEXT,
  content_markdown TEXT,
  source_event_ids TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decision_states (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  report_date TEXT NOT NULL UNIQUE,
  readiness_status TEXT NOT NULL,
  candidate_action TEXT,
  symbol TEXT,
  rule_id TEXT,
  rule_states_json TEXT NOT NULL DEFAULT '{}',
  reasons_json TEXT NOT NULL DEFAULT '[]',
  execution_status TEXT NOT NULL DEFAULT 'blocked',
  permission_status TEXT NOT NULL DEFAULT 'denied',
  proposed_amount REAL,
  proposed_currency TEXT,
  execution_reasons_json TEXT NOT NULL DEFAULT '[]',
  evidence_refs_json TEXT NOT NULL DEFAULT '[]',
  context_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS news_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  url TEXT NOT NULL UNIQUE,
  publisher TEXT,
  published_at TEXT,
  related_symbol TEXT NOT NULL,
  source TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS valuation_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  currency TEXT,
  period TEXT,
  source TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(symbol, as_of_date, metric, source)
);

CREATE TABLE IF NOT EXISTS earnings_estimate_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  fiscal_period TEXT NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  source TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(symbol, as_of_date, fiscal_period, metric, source)
);
