#!/usr/bin/env python3
"""把資料庫改成「以棚為主體」：scenes -> rooms（含自己的 tag/價格/狀態），並匯入拆解好的棚別 JSON。"""
import json, os, sqlite3, sys, glob

DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()

c.executescript("""
CREATE TABLE IF NOT EXISTS rooms (
  id          INTEGER PRIMARY KEY,
  studio_id   INTEGER NOT NULL REFERENCES studios(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  description TEXT,
  price_note  TEXT,
  status      TEXT DEFAULT 'active',      -- active / gone / limited（期間限定）
  period      TEXT,                       -- 期間限定的檔期文字
  source_url  TEXT,
  first_seen  TEXT DEFAULT (date('now','localtime')),
  last_seen   TEXT,
  UNIQUE(studio_id, name)
);
CREATE TABLE IF NOT EXISTS room_tags (
  room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  origin  TEXT DEFAULT 'auto',
  PRIMARY KEY (room_id, tag_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS rooms_fts USING fts5(
  room, description, tags, studio, city, district, address, tokenize='trigram'
);
""")
con.commit()

# 1) 把既有 scenes 搬進 rooms
try:
    for s in c.execute("SELECT * FROM scenes").fetchall():
        c.execute("""INSERT OR IGNORE INTO rooms(studio_id,name,description,source_url,first_seen,last_seen,status)
                     VALUES(?,?,?,?,?,?,?)""",
                  (s["studio_id"], s["name"], s["description"], s["source_url"],
                   s["first_seen"], s["last_seen"], "gone" if s["is_gone"] else "active"))
    con.commit()
except sqlite3.OperationalError:
    pass

# 2) 匯入拆解好的棚別
files = sorted(glob.glob(os.path.expanduser("~/rooms_*.json")))
added, skipped, unknown = 0, 0, []
for f in files:
    for entry in json.load(open(f, encoding="utf-8")):
        row = c.execute("SELECT id FROM studios WHERE name=?", (entry["studio"],)).fetchone()
        if not row:
            row = c.execute("SELECT id FROM studios WHERE name LIKE ?", (entry["studio"].split()[0] + "%",)).fetchone()
        if not row:
            unknown.append(entry["studio"]); continue
        sid = row["id"]
        for r in entry.get("rooms", []):
            name = (r.get("name") or "").strip()
            if not name: continue
            exist = c.execute("SELECT id FROM rooms WHERE studio_id=? AND name=?", (sid, name)).fetchone()
            if exist:
                rid = exist["id"]
                if r.get("desc") and not c.execute("SELECT description FROM rooms WHERE id=?", (rid,)).fetchone()[0]:
                    c.execute("UPDATE rooms SET description=? WHERE id=?", (r["desc"], rid))
                skipped += 1
            else:
                c.execute("INSERT INTO rooms(studio_id,name,description) VALUES(?,?,?)", (sid, name, r.get("desc")))
                rid = c.lastrowid; added += 1
            for t in r.get("tags", []):
                t = t.strip()
                if not t: continue
                c.execute("INSERT OR IGNORE INTO tags(name,category) VALUES(?,'style')", (t,))
                tid = c.execute("SELECT id FROM tags WHERE name=?", (t,)).fetchone()[0]
                c.execute("INSERT OR IGNORE INTO room_tags(room_id,tag_id) VALUES(?,?)", (rid, tid))
con.commit()

# 3) 店家層級的 tag 改成「所屬各棚 tag 的聯集」，保留原本從特色抽的當備援
for sid, in c.execute("SELECT id FROM studios").fetchall():
    for tid, in c.execute("SELECT DISTINCT rt.tag_id FROM room_tags rt JOIN rooms r ON r.id=rt.room_id WHERE r.studio_id=?", (sid,)).fetchall():
        c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) VALUES(?,?,'derived')", (sid, tid))
con.commit()

# 4) 重建棚層級全文索引
c.execute("DELETE FROM rooms_fts")
for r in c.execute("""SELECT r.id, r.name, r.description, s.name, s.city, s.district, s.address,
       (SELECT group_concat(t.name,' ') FROM room_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.room_id=r.id)
       FROM rooms r JOIN studios s ON s.id=r.studio_id""").fetchall():
    c.execute("INSERT INTO rooms_fts(rowid,room,description,tags,studio,city,district,address) VALUES(?,?,?,?,?,?,?,?)",
              (r[0], r[1] or "", r[2] or "", r[7] or "", r[3] or "", r[4] or "", r[5] or "", r[6] or ""))
con.commit()

print(f"新增棚 {added}、已存在 {skipped}、找不到對應店家 {len(unknown)}")
if unknown: print("  對不上的店名：", ", ".join(sorted(set(unknown))))
print("棚總數", c.execute("SELECT COUNT(*) FROM rooms").fetchone()[0],
      "｜有棚資料的店", c.execute("SELECT COUNT(DISTINCT studio_id) FROM rooms").fetchone()[0],
      "｜tag", c.execute("SELECT COUNT(*) FROM tags").fetchone()[0])
