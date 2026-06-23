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
