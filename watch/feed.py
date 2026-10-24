#!/usr/bin/env python3
"""比對外部清單（如 PONPAI「最新攝影場地」）有沒有沒看過的項目。
用法：echo '{"feed":"ponpai_latest","items":[{"name":"XX棚","url":"..."}]}' | python3 feed.py
會印出「這次才第一次出現」的項目，並把全部項目記進 feed_seen。

同一家店 PONPAI 首頁常常換寫法（「【七號盒子攝影棚】–內湖棚4樓」「七號盒子攝影棚 內湖棚」…），
所以除了名稱，也用網址判斷有沒有看過；網址相同就不算新店，只把新寫法記下來。
已入庫的店（studios.check_url 或 sources.url 相同）也不算新店。
"""
import json, sqlite3, sys, os, urllib.parse
DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))

def norm_url(u):
    if not u: return None
    p = urllib.parse.urlsplit(u.strip())
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))

d = json.load(sys.stdin)
con = sqlite3.connect(DB); c = con.cursor()
feed = d.get("feed", "ponpai_latest")
seen_urls = {norm_url(u) for (u,) in c.execute("SELECT url FROM feed_seen WHERE feed=? AND url IS NOT NULL", (feed,))}
seen_urls |= {norm_url(u) for (u,) in c.execute("SELECT check_url FROM studios WHERE check_url IS NOT NULL")}
seen_urls |= {norm_url(u) for (u,) in c.execute("SELECT url FROM sources")}
seen_urls.discard(None)
new = []
for it in d["items"]:
    name = it["name"].strip() if isinstance(it, dict) else str(it).strip()
    url = it.get("url") if isinstance(it, dict) else None
    seen_name = c.execute("SELECT 1 FROM feed_seen WHERE feed=? AND item=?", (feed, name)).fetchone()
    seen_url = norm_url(url) in seen_urls if url else False
    if not seen_name:
        c.execute("INSERT OR IGNORE INTO feed_seen(feed,item,url) VALUES(?,?,?)", (feed, name, url))
    if not seen_name and not seen_url:
        new.append({"name": name, "url": url})
    if url: seen_urls.add(norm_url(url))
con.commit()
print(json.dumps({"feed": feed, "total": len(d["items"]), "new": new}, ensure_ascii=False, indent=1))
