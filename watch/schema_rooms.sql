CREATE TABLE IF NOT EXISTS rooms (
  id INTEGER PRIMARY KEY,
  studio_id INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  name TEXT NOT NULL, description TEXT, price_note TEXT,
  status TEXT DEFAULT 'active', period TEXT, source_url TEXT,
  first_seen TEXT DEFAULT (date('now','localtime')), last_seen TEXT,
  UNIQUE(studio_id, name)
);
CREATE TABLE IF NOT EXISTS room_tags (
  room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  origin TEXT DEFAULT 'auto', PRIMARY KEY (room_id, tag_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS rooms_fts USING fts5(
  room, description, tags, studio, city, district, address, tokenize='trigram'
);
CREATE TABLE IF NOT EXISTS feed_seen (
  id INTEGER PRIMARY KEY, feed TEXT NOT NULL, item TEXT NOT NULL, url TEXT,
  first_seen TEXT DEFAULT (date('now','localtime')), note TEXT, UNIQUE(feed, item)
);
