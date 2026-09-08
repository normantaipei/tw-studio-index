#!/usr/bin/env python3
"""從 watch/data/*.jsonl 重建 studios.db（clone 下來後跑這支就有完整資料庫）。
用法：python3 build_db.py [輸出路徑]"""
import json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
if os.path.exists(OUT): os.remove(OUT)
con = sqlite3.connect(OUT); c = con.cursor()
c.executescript(open(os.path.join(HERE, "schema.sql"), encoding="utf-8").read().replace("PRAGMA journal_mode=WAL;", ""))
c.executescript(open(os.path.join(HERE, "schema_rooms.sql"), encoding="utf-8").read())

def rows(f):
    p = os.path.join(DATA, f)
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []

for t in rows("tags.jsonl"):
    c.execute("INSERT OR IGNORE INTO tags(name,category) VALUES(?,?)", (t["name"], t.get("category")))

def tag_id(name):
    c.execute("INSERT OR IGNORE INTO tags(name,category) VALUES(?,'style')", (name,))
    return c.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()[0]

sid_by_name = {}
photo_links = []
for s in rows("studios.jsonl"):
    srcs, photos, tags = s.pop("sources", []), s.pop("photos", []), s.pop("tags", [])
    cols = ",".join(s.keys()); ph = ",".join("?" * len(s))
    c.execute(f"INSERT INTO studios({cols}) VALUES({ph})", list(s.values()))
    sid = c.lastrowid; sid_by_name[s["name"]] = sid
    for x in srcs:
        c.execute("INSERT OR IGNORE INTO sources(studio_id,kind,url,is_primary) VALUES(?,?,?,?)",
                  (sid, x.get("kind"), x["url"], x.get("is_primary", 0)))
    for ph in photos:
        if isinstance(ph, str):
            c.execute("INSERT OR IGNORE INTO photos(studio_id,url) VALUES(?,?)", (sid, ph))
        else:
            c.execute("INSERT OR IGNORE INTO photos(studio_id,url,local_path) VALUES(?,?,?)",
                      (sid, ph["url"], ph.get("local_path")))
            if ph.get("room"):
                photo_links.append((sid, ph["room"], ph["url"]))   # 棚還沒建，稍後再連
    for t in tags:
        c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) VALUES(?,?,'manual')", (sid, tag_id(t)))

for r in rows("rooms.jsonl"):
    studio = r.pop("studio"); tags = r.pop("tags", [])
    sid = sid_by_name.get(studio)
    if not sid: continue
    r["studio_id"] = sid
    cols = ",".join(r.keys()); ph = ",".join("?" * len(r))
    c.execute(f"INSERT INTO rooms({cols}) VALUES({ph})", list(r.values()))
    rid = c.lastrowid
    for t in tags:
        c.execute("INSERT OR IGNORE INTO room_tags(room_id,tag_id) VALUES(?,?)", (rid, tag_id(t)))

# 棚都建好之後，再把照片連到棚
for sid, room_name, url in photo_links:
    c.execute("""UPDATE photos SET room_id=(SELECT id FROM rooms WHERE studio_id=? AND name=?)
                 WHERE studio_id=? AND url=?""", (sid, room_name, sid, url))

for ch in rows("changes.jsonl"):
    studio = ch.pop("studio", None)
    c.execute("""INSERT INTO changes(studio_id,studio_name,detected_at,type,summary,detail,source_url,seen)
                 VALUES(?,?,?,?,?,?,?,?)""",
              (sid_by_name.get(studio), studio, ch["detected_at"], ch["type"], ch["summary"],
               ch.get("detail"), ch.get("source_url"), ch.get("seen", 0)))
for f in rows("feed_seen.jsonl"):
    c.execute("INSERT OR IGNORE INTO feed_seen(feed,item,url,first_seen) VALUES(?,?,?,?)",
              (f["feed"], f["item"], f.get("url"), f.get("first_seen")))

# 店家 tag = 各棚 tag 聯集
for (sid,) in c.execute("SELECT id FROM studios").fetchall():
    for (tid,) in c.execute("SELECT DISTINCT rt.tag_id FROM room_tags rt JOIN rooms r ON r.id=rt.room_id WHERE r.studio_id=?", (sid,)).fetchall():
        c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) VALUES(?,?,'derived')", (sid, tid))
con.commit()
os.system(f'STUDIO_DB="{OUT}" python3 "{os.path.join(HERE, "studio.py")}" reindex >/dev/null')
print("已重建", OUT, "｜店家", c.execute("SELECT COUNT(*) FROM studios").fetchone()[0],
      "｜棚", c.execute("SELECT COUNT(*) FROM rooms").fetchone()[0])
