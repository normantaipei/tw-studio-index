#!/usr/bin/env python3
"""比對外部清單（如 PONPAI「最新攝影場地」）有沒有沒看過的項目。
用法：echo '{"feed":"ponpai_latest","items":[{"name":"XX棚","url":"..."}]}' | python3 feed.py
會印出「這次才第一次出現」的項目，並把全部項目記進 feed_seen。
"""
import json, sqlite3, sys, os
DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
d = json.load(sys.stdin)
con = sqlite3.connect(DB); c = con.cursor()
feed = d.get("feed", "ponpai_latest")
new = []
for it in d["items"]:
    name = it["name"].strip() if isinstance(it, dict) else str(it).strip()
    url = it.get("url") if isinstance(it, dict) else None
    seen = c.execute("SELECT 1 FROM feed_seen WHERE feed=? AND item=?", (feed, name)).fetchone()
    if not seen:
        c.execute("INSERT OR IGNORE INTO feed_seen(feed,item,url) VALUES(?,?,?)", (feed, name, url))
        new.append({"name": name, "url": url})
con.commit()
print(json.dumps({"feed": feed, "total": len(d["items"]), "new": new}, ensure_ascii=False, indent=1))
