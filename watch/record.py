#!/usr/bin/env python3
"""把一次檢查的結果寫進 studios.db。用法： python3 record.py < result.json
JSON 格式：
{
 "cohort": 2,
 "notes": "選填",
 "results": [
   {"studio_id": 12,
    "verdict": "open|suspect_closed|closed|moved|unknown|unreachable",
    "method": "gmap|webfetch|websearch|mixed",
    "source_url": "...",
    "evidence": "Google 地圖顯示營業中、官網 2026/08 有更新",
    "address": "（選填，抓到新地址才填）",
    "price_note": "（選填）",
    "check_url": "https://.../scene.html",   // 這次實際用來確認的網址（下次巡檢會直接打這個，省下重新搜尋）
    "gmap_url": "https://www.google.com/maps/place/...",  // 解析到的 Google 地圖頁（選填）
    "rooms": [{"name":"歐式書房","desc":"...","tags":["歐風","書房"],"url":"該棚所在頁面（選填）"}],
    "rooms_complete": true,                   // 是否為該店完整棚別清單（true 才會判斷棚被撤掉）
    "photos": [{"url":"https://.../scene1.jpg","room":"歐式書房（選填）"}],   // 這次在頁面上看到的新場景照
    "new_sources": [{"kind":"official","url":"https://..."}],
    "changes": [{"type":"price","summary":"...","detail":"...","source_url":"..."}]  // 額外異動
   }
 ],
 "new_studios": [
   {"name":"XX攝影棚","city":"台北市","district":"中山區","address":"...","features":"...",
    "source_url":"https://...","tags":["歐風"],"detail":"PONPAI 新上架"}
 ]
}
"""
import json, sqlite3, sys, os, datetime

DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
data = json.load(sys.stdin)
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()
today = datetime.date.today().isoformat()
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
changes_found = 0

def add_change(sid, name, typ, summary, detail=None, url=None):
    global changes_found
    c.execute("""INSERT INTO changes(studio_id,studio_name,detected_at,type,summary,detail,source_url)
                 VALUES(?,?,?,?,?,?,?)""", (sid, name, now, typ, summary, detail, url))
    changes_found += 1

for r in data.get("results", []):
    sid = r["studio_id"]
    row = c.execute("SELECT * FROM studios WHERE id=?", (sid,)).fetchone()
    if not row:
        print(f"⚠️ 找不到 studio_id={sid}"); continue
    old_status, name = row["status"], row["name"]
    verdict = r.get("verdict", "unknown")
    c.execute("""INSERT INTO checks(studio_id,checked_at,method,source_url,verdict,evidence)
                 VALUES(?,?,?,?,?,?)""",
              (sid, now, r.get("method"), r.get("source_url"), verdict, r.get("evidence")))
    if verdict not in ("unknown", "unreachable") and verdict != old_status:
        typ = {"closed":"closed","suspect_closed":"suspect_closed","moved":"moved"}.get(verdict, "reopened")
        if not (old_status == "unknown" and verdict == "open"):     # 首次確認營業中不算異動
            label = {"closed":"已歇業","suspect_closed":"疑似歇業","moved":"已搬遷","open":"恢復營業"}[verdict]
            add_change(sid, name, typ, f"{name} {label}", r.get("evidence"), r.get("source_url"))
        c.execute("UPDATE studios SET status=?, status_note=?, last_changed=? WHERE id=?",
                  (verdict, r.get("evidence"), today, sid))
    elif verdict not in ("unknown", "unreachable"):
        c.execute("UPDATE studios SET status=?, status_note=? WHERE id=?", (verdict, r.get("evidence"), sid))
    c.execute("UPDATE studios SET last_checked=? WHERE id=?", (today, sid))
    if r.get("address") and r["address"] != (row["address"] or ""):
        if row["address"]:
            add_change(sid, name, "moved", f"{name} 地址有變動", f'舊：{row["address"]}\n新：{r["address"]}', r.get("source_url"))
        c.execute("UPDATE studios SET address=? WHERE id=?", (r["address"], sid))
    if r.get("price_note"):
        old = row["price_note"] or ""
        if old and old != r["price_note"]:
            add_change(sid, name, "price", f"{name} 價格資訊更新", f'舊：{old}\n新：{r["price_note"]}', r.get("source_url"))
        c.execute("UPDATE studios SET price_note=? WHERE id=?", (r["price_note"], sid))

    rooms = r.get("rooms") or r.get("scenes") or []
    rooms = [({"name": x} if isinstance(x, str) else x) for x in rooms]
    if rooms:
        known = {x["name"]: x["id"] for x in c.execute("SELECT id,name FROM rooms WHERE studio_id=?", (sid,))}
        baselined = row["baseline_done"]
        seen_names = []
        for rm in rooms:
            rname = (rm.get("name") or "").strip()
            if not rname: continue
            seen_names.append(rname)
            if rname in known:
                rid = known[rname]
                c.execute("UPDATE rooms SET last_seen=?, status=CASE WHEN status='gone' THEN 'active' ELSE status END WHERE id=?",
                          (today, rid))
                if rm.get("desc"):
                    c.execute("UPDATE rooms SET description=COALESCE(NULLIF(description,''),?) WHERE id=?", (rm["desc"], rid))
            else:
                c.execute("""INSERT INTO rooms(studio_id,name,description,price_note,status,period,source_url,first_seen,last_seen)
                             VALUES(?,?,?,?,?,?,?,?,?)""",
                          (sid, rname, rm.get("desc"), rm.get("price"), rm.get("status","active"),
                           rm.get("period"), rm.get("url") or r.get("check_url") or r.get("source_url"), today, today))
                rid = c.lastrowid
                if baselined:
                    add_change(sid, name, "new_room", f"{name} 有新棚：{rname}",
                               rm.get("desc") or rm.get("period"), r.get("source_url"))
            for t in rm.get("tags", []):
                t = t.strip()
                if not t: continue
                c.execute("INSERT OR IGNORE INTO tags(name,category) VALUES(?,'style')", (t,))
                tid = c.execute("SELECT id FROM tags WHERE name=?", (t,)).fetchone()[0]
                c.execute("INSERT OR IGNORE INTO room_tags(room_id,tag_id) VALUES(?,?)", (rid, tid))
        if r.get("rooms_complete") or r.get("scenes_complete"):
            for old_name, oid in known.items():
                if old_name not in seen_names:
                    was = c.execute("SELECT status FROM rooms WHERE id=?", (oid,)).fetchone()[0]
                    c.execute("UPDATE rooms SET status='gone' WHERE id=?", (oid,))
                    if baselined and was != 'gone':
                        add_change(sid, name, "room_gone", f"{name} 的「{old_name}」已從官網撤下", None, r.get("source_url"))
        c.execute("UPDATE studios SET baseline_done=1 WHERE id=?", (sid,))

    if r.get("check_url"):
        old_cu = row["check_url"] if "check_url" in row.keys() else None
        c.execute("UPDATE studios SET check_url=?, check_note=? WHERE id=?",
                  (r["check_url"], r.get("check_note") or "巡檢實際使用", sid))
        if old_cu and old_cu != r["check_url"]:
            add_change(sid, name, "source_found", f"{name} 的巡檢網址換成更好的來源", f"舊：{old_cu}\n新：{r['check_url']}", r["check_url"])
    if r.get("gmap_url"):
        c.execute("UPDATE studios SET gmap_url=? WHERE id=?", (r["gmap_url"], sid))

    for ph in r.get("photos", []):
        purl = (ph.get("url") if isinstance(ph, dict) else ph) or ""
        if not purl.startswith("http"): continue
        prid = None
        if isinstance(ph, dict) and ph.get("room"):
            got = c.execute("SELECT id FROM rooms WHERE studio_id=? AND name=?", (sid, ph["room"])).fetchone()
            prid = got["id"] if got else None
        if not c.execute("SELECT 1 FROM photos WHERE studio_id=? AND url=?", (sid, purl)).fetchone():
            c.execute("INSERT INTO photos(studio_id,room_id,url) VALUES(?,?,?)", (sid, prid, purl))
        elif prid:
            c.execute("UPDATE photos SET room_id=? WHERE studio_id=? AND url=? AND room_id IS NULL", (prid, sid, purl))

    for ns in r.get("new_sources", []):
        exists = c.execute("SELECT 1 FROM sources WHERE studio_id=? AND url=?", (sid, ns["url"])).fetchone()
        c.execute("INSERT OR IGNORE INTO sources(studio_id,kind,url,is_primary,last_status,last_ok_at) VALUES(?,?,?,?,?,?)",
                  (sid, ns.get("kind","other"), ns["url"], 1 if ns.get("kind") in ("official","booking") else 0, "ok", today))
        if not exists:
            add_change(sid, name, "source_found", f'{name} 找到新的公開來源', ns["url"], ns["url"])

    for ch in r.get("changes", []):
        add_change(sid, name, ch.get("type","other"), ch["summary"], ch.get("detail"), ch.get("source_url"))

for n in data.get("new_studios", []):
    exists = c.execute("SELECT id FROM studios WHERE name=? OR aliases LIKE ?", (n["name"], f'%{n["name"]}%')).fetchone()
    if exists:
        continue
    cohort = c.execute("SELECT cohort FROM studios GROUP BY cohort ORDER BY COUNT(*) ASC LIMIT 1").fetchone()[0]
    c.execute("""INSERT INTO studios(name,city,district,address,features,cohort,status,first_seen,last_checked)
                 VALUES(?,?,?,?,?,?, 'open', ?, ?)""",
              (n["name"], n.get("city"), n.get("district"), n.get("address"), n.get("features"), cohort, today, today))
    sid = c.lastrowid
    if n.get("source_url"):
        c.execute("INSERT OR IGNORE INTO sources(studio_id,kind,url,is_primary) VALUES(?,?,?,1)",
                  (sid, n.get("source_kind","other"), n["source_url"]))
    for t in n.get("tags", []):
        c.execute("INSERT OR IGNORE INTO tags(name,category) VALUES(?,'style')", (t,))
        tid = c.execute("SELECT id FROM tags WHERE name=?", (t,)).fetchone()[0]
        c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) VALUES(?,?,'auto')", (sid, tid))
    add_change(sid, n["name"], "new_studio",
               f'新開棚：{n["name"]}（{n.get("city","")}{n.get("district","")}）',
               n.get("detail") or n.get("features"), n.get("source_url"))

c.execute("INSERT INTO runs(ran_at,cohort,studios_checked,changes_found,notes) VALUES(?,?,?,?,?)",
          (now, data.get("cohort"), len(data.get("results", [])), changes_found, data.get("notes")))
con.commit()

# 重建全文索引
c.execute("DELETE FROM rooms_fts")
for r in c.execute("""SELECT r.id,r.name,r.description,s.name,s.city,s.district,s.address,
    (SELECT group_concat(t.name,' ') FROM room_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.room_id=r.id)
    FROM rooms r JOIN studios s ON s.id=r.studio_id""").fetchall():
    c.execute("INSERT INTO rooms_fts(rowid,room,description,tags,studio,city,district,address) VALUES(?,?,?,?,?,?,?,?)",
              (r[0], r[1] or "", r[2] or "", r[7] or "", r[3] or "", r[4] or "", r[5] or "", r[6] or ""))
c.execute("DELETE FROM studios_fts")
for row in c.execute("""SELECT s.id,s.name,s.aliases,s.city,s.district,s.address,s.features,
    (SELECT group_concat(t.name,' ') FROM studio_tags st JOIN tags t ON t.id=st.tag_id WHERE st.studio_id=s.id),
    (SELECT group_concat(rm.name,' ') FROM rooms rm WHERE rm.studio_id=s.id AND rm.status!='gone') FROM studios s""").fetchall():
    c.execute("INSERT INTO studios_fts(rowid,name,aliases,city,district,address,features,tags,scenes) VALUES(?,?,?,?,?,?,?,?,?)",
              (row[0],) + tuple(x or "" for x in row[1:]))
# 店家 tag = 各棚 tag 聯集
for sid_, in c.execute("SELECT id FROM studios").fetchall():
    for tid_, in c.execute("SELECT DISTINCT rt.tag_id FROM room_tags rt JOIN rooms rr ON rr.id=rt.room_id WHERE rr.studio_id=?", (sid_,)).fetchall():
        c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) VALUES(?,?,'derived')", (sid_, tid_))
con.commit()
print(json.dumps({"checked": len(data.get("results", [])), "new_studios": len(data.get("new_studios", [])),
                  "changes_found": changes_found}, ensure_ascii=False))
