PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS studios (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  aliases       TEXT DEFAULT '',
  city          TEXT,
  district      TEXT,
  address       TEXT,
  features      TEXT,
  price_note    TEXT,
  status        TEXT DEFAULT 'unknown',      -- open / suspect_closed / closed / moved / unknown
  status_note   TEXT,
  fb_only       INTEGER DEFAULT 0,
  cohort        INTEGER,                      -- 0-6，每日輪掃分組
  first_seen    TEXT DEFAULT (date('now','localtime')),
  last_checked  TEXT,
  last_changed  TEXT,
  notes         TEXT,
  baseline_done INTEGER DEFAULT 0,
  check_url     TEXT,                          -- 每日巡檢固定打這個網址
  check_note    TEXT,                          -- 這個網址是什麼類型的來源
  gmap_url      TEXT                            -- Google 地圖頁（確認營業狀態用）
);

CREATE TABLE IF NOT EXISTS sources (
  id            INTEGER PRIMARY KEY,
  studio_id     INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  kind          TEXT,                         -- official/booking/ponpai/ig/fb/threads/blog/gmap/other
  url           TEXT NOT NULL,
  is_primary    INTEGER DEFAULT 0,
  last_status   TEXT,                         -- ok / 404 / dead / blocked
  last_ok_at    TEXT,
  dead_since    TEXT,
  UNIQUE(studio_id, url)
);

CREATE TABLE IF NOT EXISTS scenes (
  id            INTEGER PRIMARY KEY,
  studio_id     INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  description   TEXT,
  source_url    TEXT,
  first_seen    TEXT DEFAULT (date('now','localtime')),
  last_seen     TEXT,
  is_gone       INTEGER DEFAULT 0,
  UNIQUE(studio_id, name)
);

CREATE TABLE IF NOT EXISTS photos (
  id            INTEGER PRIMARY KEY,
  studio_id     INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  scene_id      INTEGER REFERENCES scenes(id) ON DELETE SET NULL,
  url           TEXT NOT NULL,
  added_at      TEXT DEFAULT (date('now','localtime')),
  room_id       INTEGER,                      -- 屬於哪個棚（可空）
  local_path    TEXT,                         -- docs/ 下的本地 webp 相對路徑
  fetched_at    TEXT,
  fetch_error   TEXT,
  UNIQUE(studio_id, url)
);

CREATE TABLE IF NOT EXISTS tags (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  category      TEXT                          -- style / facility / usage / area
);

CREATE TABLE IF NOT EXISTS studio_tags (
  studio_id     INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  tag_id        INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  origin        TEXT DEFAULT 'auto',          -- auto / manual
  PRIMARY KEY (studio_id, tag_id)
);

CREATE TABLE IF NOT EXISTS checks (
  id            INTEGER PRIMARY KEY,
  studio_id     INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  checked_at    TEXT DEFAULT (datetime('now','localtime')),
  method        TEXT,                         -- webfetch / websearch / gmap
  source_url    TEXT,
  verdict       TEXT,                         -- open / suspect_closed / closed / unknown / unreachable
  evidence      TEXT,
  content_hash  TEXT
);
CREATE INDEX IF NOT EXISTS idx_checks_studio ON checks(studio_id, checked_at);

CREATE TABLE IF NOT EXISTS changes (
  id            INTEGER PRIMARY KEY,
  studio_id     INTEGER REFERENCES studios(id) ON DELETE CASCADE,
  studio_name   TEXT,                         -- 新開棚尚未入庫時也能記
  detected_at   TEXT DEFAULT (datetime('now','localtime')),
  type          TEXT NOT NULL,                -- new_studio / new_scene / closed / suspect_closed / reopened / moved / price / renamed / site_dead
  summary       TEXT NOT NULL,
  detail        TEXT,
  source_url    TEXT,
  seen          INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_changes_time ON changes(detected_at);

CREATE TABLE IF NOT EXISTS snapshots (
  id            INTEGER PRIMARY KEY,
  studio_id     INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  source_id     INTEGER REFERENCES sources(id) ON DELETE CASCADE,
  fetched_at    TEXT DEFAULT (datetime('now','localtime')),
  content_hash  TEXT,
  scene_list    TEXT,                         -- 當次抓到的造景名稱清單（換行分隔）
  summary       TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_studio ON snapshots(studio_id, fetched_at);

CREATE TABLE IF NOT EXISTS runs (
  id            INTEGER PRIMARY KEY,
  ran_at        TEXT DEFAULT (datetime('now','localtime')),
  cohort        INTEGER,
  studios_checked INTEGER DEFAULT 0,
  changes_found INTEGER DEFAULT 0,
  notes         TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS studios_fts USING fts5(
  name, aliases, city, district, address, features, tags, scenes, tokenize='trigram'
);
