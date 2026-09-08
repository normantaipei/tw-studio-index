#!/usr/bin/env python3
"""把爬回來的 photos_part*.json 匯進 photos 表（可對應到棚）。"""
import json, os, sqlite3, glob, re
DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
SKIP_STUDIOS = {"曙暮光工作室"}   # 來源頁疑似不同店家，待人工確認
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()
added = dup = skipped = 0; unknown = []
for f in sorted(glob.glob(os.path.expanduser("~/photos_part*.json"))):
    for e in json.load(open(f, encoding="utf-8")):
        row = c.execute("SELECT id FROM studios WHERE name=?", (e["studio"],)).fetchone()
        if not row: unknown.append(e["studio"]); continue
        if e["studio"] in SKIP_STUDIOS:
            skipped += len(e.get("photos", [])); continue
        sid = row["id"]
        rooms = {r["name"]: r["id"] for r in c.execute("SELECT id,name FROM rooms WHERE studio_id=?", (sid,))}
        for p in e.get("photos", []):
            url = (p.get("url") or "").strip()
            if not re.match(r"^https?://", url) or len(url) < 20: continue
            rid = rooms.get((p.get("room") or "").strip()) if p.get("room") else None
            if c.execute("SELECT 1 FROM photos WHERE studio_id=? AND url=?", (sid, url)).fetchone():
                if rid: c.execute("UPDATE photos SET room_id=? WHERE studio_id=? AND url=? AND room_id IS NULL", (rid, sid, url))
                dup += 1; continue
            c.execute("INSERT INTO photos(studio_id,room_id,url) VALUES(?,?,?)", (sid, rid, url))
            added += 1
con.commit()
print(f"新增 {added} 張、重複 {dup} 張、跳過 {skipped} 張（待確認店家）")
if unknown: print("對不到店名：", set(unknown))
print("照片總數", c.execute("SELECT COUNT(*) FROM photos").fetchone()[0],
      "｜對應到棚的", c.execute("SELECT COUNT(*) FROM photos WHERE room_id IS NOT NULL").fetchone()[0])
print("有照片的店", c.execute("SELECT COUNT(DISTINCT studio_id) FROM photos").fetchone()[0], "/ 94")
print("有圖可顯示的棚", c.execute("""SELECT COUNT(*) FROM rooms r WHERE EXISTS(SELECT 1 FROM photos p WHERE p.studio_id=r.studio_id)""").fetchone()[0],
      "/", c.execute("SELECT COUNT(*) FROM rooms").fetchone()[0])
