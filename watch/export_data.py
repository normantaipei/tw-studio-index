#!/usr/bin/env python3
"""把 studios.db 匯出成可進版控的 JSONL 文字檔（watch/data/）。
排序固定、UTF-8 不跳脫，所以 git diff 看得出實際變了什麼。"""
import json, os, sqlite3
DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()

def dump(fname, rows):
    path = os.path.join(OUT, fname)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"{fname}: {len(rows)} 筆")

studios = []
for s in c.execute("SELECT * FROM studios ORDER BY name").fetchall():
    d = dict(s)
    d.pop("id", None)
    d["sources"] = [dict(kind=x["kind"], url=x["url"], is_primary=x["is_primary"])
                    for x in c.execute("SELECT kind,url,is_primary FROM sources WHERE studio_id=? ORDER BY url", (s["id"],))]
    d["photos"] = [dict(url=x["url"], room=x["room"], local_path=x["local_path"]) for x in c.execute(
        """SELECT p.url, p.local_path, r.name room FROM photos p LEFT JOIN rooms r ON r.id=p.room_id
           WHERE p.studio_id=? ORDER BY p.url""", (s["id"],)).fetchall()]
    d["tags"] = sorted(x[0] for x in c.execute(
        "SELECT t.name FROM studio_tags st JOIN tags t ON t.id=st.tag_id WHERE st.studio_id=? AND st.origin='manual'", (s["id"],)))
    studios.append(d)
dump("studios.jsonl", studios)

rooms = []
for r in c.execute("""SELECT r.*, s.name studio FROM rooms r JOIN studios s ON s.id=r.studio_id
                      ORDER BY s.name, r.name""").fetchall():
    d = dict(r); rid = d.pop("id"); d.pop("studio_id")
    d["tags"] = sorted(x[0] for x in c.execute(
        "SELECT t.name FROM room_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.room_id=?", (rid,)))
    rooms.append(d)
dump("rooms.jsonl", rooms)

changes = [dict(x) for x in c.execute("""SELECT c.detected_at,c.type,c.summary,c.detail,c.source_url,c.seen,
                                          s.name studio FROM changes c LEFT JOIN studios s ON s.id=c.studio_id
                                          ORDER BY c.detected_at, c.type""").fetchall()]
dump("changes.jsonl", changes)

feed = [dict(x) for x in c.execute("SELECT feed,item,url,first_seen FROM feed_seen ORDER BY feed,item").fetchall()]
dump("feed_seen.jsonl", feed)

tags = [dict(name=x["name"], category=x["category"]) for x in c.execute("SELECT name,category FROM tags ORDER BY name").fetchall()]
dump("tags.jsonl", tags)
