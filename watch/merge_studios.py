#!/usr/bin/env python3
"""資料庫整理工具：合併重複店家／重複棚、清重複照片、重置可重試的下載錯誤。

  python3 merge_studios.py merge 40 124 125 126 --name "七號盒子攝影棚 內湖棚4樓"
      把 124/125/126 併進 40：棚、照片、檢查紀錄、來源、異動全部搬過去，被併掉的名稱記成別名，
      假的 new_studio 異動刪掉，最後刪除重複店家。
  python3 merge_studios.py merge-rooms 518 513 524 532
      同一家店裡其實是同一個棚的多筆 rooms 併成一筆（照片 room_id 跟著搬、tag 聯集）。
  python3 merge_studios.py dedupe-photos [--dry-run]
      同一家店同一張圖只差 query（PONPAI ?img_resize_type=high）的重複紀錄只留一筆，
      多餘的 webp 檔一起刪。
  python3 merge_studios.py reset-errors --like ascii
      把 fetch_error 含指定字串的照片錯誤清掉，下次 fetch_photos.py 會重抓。

改完記得 python3 export_data.py 讓變更進版控。
"""
import argparse, os, sqlite3, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("STUDIO_DB", os.path.join(HERE, "studios.db"))
DOCS = os.path.join(os.path.dirname(HERE), "docs")

def conn():
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=OFF")
    return c

def photo_key(url):
    p = urllib.parse.urlsplit(url)
    q = "" if p.netloc.endswith("asset.ponpai.tw") else p.query
    return (p.netloc, p.path, q)

def cmd_merge(a):
    c = conn(); keep = a.keep
    k = c.execute("SELECT * FROM studios WHERE id=?", (keep,)).fetchone()
    if not k: raise SystemExit(f"找不到 studio #{keep}")
    aliases = [x for x in (k["aliases"] or "").split("|") if x]
    for dup in a.dups:
        d = c.execute("SELECT * FROM studios WHERE id=?", (dup,)).fetchone()
        if not d: print(f"略過：找不到 #{dup}"); continue
        print(f"併 #{dup} {d['name']} → #{keep} {k['name']}")
        if d["name"] not in aliases and d["name"] != k["name"]: aliases.append(d["name"])
        # 棚：同名的併入既有棚，不同名的整筆搬過去
        for r in c.execute("SELECT id,name FROM rooms WHERE studio_id=?", (dup,)).fetchall():
            same = c.execute("SELECT id FROM rooms WHERE studio_id=? AND name=?", (keep, r["name"])).fetchone()
            if same:
                _merge_room(c, same["id"], r["id"])
            else:
                c.execute("UPDATE rooms SET studio_id=? WHERE id=?", (keep, r["id"]))
        # 照片：(studio_id,url) 有唯一限制，兩邊都有的那張只留一筆（保留有本地檔的那份）
        for ph in c.execute("SELECT id,url,local_path,room_id FROM photos WHERE studio_id=?", (dup,)).fetchall():
            same = c.execute("SELECT id,local_path,room_id FROM photos WHERE studio_id=? AND url=?", (keep, ph["url"])).fetchone()
            if same:
                if not same["local_path"] and ph["local_path"]:
                    c.execute("UPDATE photos SET local_path=?, fetch_error=NULL WHERE id=?", (ph["local_path"], same["id"]))
                elif ph["local_path"] and ph["local_path"] != same["local_path"]:
                    pth = os.path.join(DOCS, ph["local_path"])
                    if os.path.exists(pth): os.remove(pth)
                if not same["room_id"] and ph["room_id"]:
                    c.execute("UPDATE photos SET room_id=? WHERE id=?", (ph["room_id"], same["id"]))
                c.execute("DELETE FROM photos WHERE id=?", (ph["id"],))
        c.execute("UPDATE photos SET studio_id=? WHERE studio_id=?", (keep, dup))
        c.execute("UPDATE checks SET studio_id=? WHERE studio_id=?", (keep, dup))
        c.execute("DELETE FROM changes WHERE studio_id=? AND type='new_studio'", (dup,))
        c.execute("UPDATE changes SET studio_id=?, studio_name=? WHERE studio_id=?", (keep, k["name"], dup))
        for s in c.execute("SELECT kind,url,is_primary FROM sources WHERE studio_id=?", (dup,)).fetchall():
            if not c.execute("SELECT 1 FROM sources WHERE studio_id=? AND url=?", (keep, s["url"])).fetchone():
                c.execute("INSERT INTO sources(studio_id,kind,url,is_primary) VALUES(?,?,?,?)", (keep, s["kind"], s["url"], s["is_primary"]))
        c.execute("DELETE FROM sources WHERE studio_id=?", (dup,))
        c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) SELECT ?,tag_id,origin FROM studio_tags WHERE studio_id=?", (keep, dup))
        c.execute("DELETE FROM studio_tags WHERE studio_id=?", (dup,))
        for t in ("snapshots", "scenes"):
            try: c.execute(f"UPDATE {t} SET studio_id=? WHERE studio_id=?", (keep, dup))
            except sqlite3.OperationalError: pass
        # 補空欄位
        for col in ("address", "check_url", "gmap_url", "features", "price_note"):
            if not k[col] and d[col]:
                c.execute(f"UPDATE studios SET {col}=? WHERE id=?", (d[col], keep))
        c.execute("DELETE FROM studios WHERE id=?", (dup,))
    if a.name and a.name != k["name"]:
        if k["name"] not in aliases: aliases.append(k["name"])
        aliases = [x for x in aliases if x != a.name]
        c.execute("UPDATE studios SET name=? WHERE id=?", (a.name, keep))
        c.execute("UPDATE changes SET studio_name=? WHERE studio_id=?", (a.name, keep))
    c.execute("UPDATE studios SET aliases=? WHERE id=?", ("|".join(aliases), keep))
    # 棚照片去重後，重複的 rooms 若剛好同名也會在上面併掉；這裡順手重算 last_checked
    c.execute("UPDATE studios SET last_checked=(SELECT substr(max(checked_at),1,10) FROM checks WHERE studio_id=?) WHERE id=?", (keep, keep))
    c.commit()
    _reindex(c)
    print(f"完成。#{keep} 現在：{c.execute('SELECT name FROM studios WHERE id=?', (keep,)).fetchone()[0]}；別名：{' | '.join(aliases) or '-'}")
    print("棚：", [r[0] for r in c.execute("SELECT name FROM rooms WHERE studio_id=?", (keep,))])
    print("照片：", c.execute("SELECT COUNT(*) FROM photos WHERE studio_id=?", (keep,)).fetchone()[0])

def _merge_room(c, keep, dup):
    c.execute("UPDATE photos SET room_id=? WHERE room_id=?", (keep, dup))
    c.execute("INSERT OR IGNORE INTO room_tags(room_id,tag_id,origin) SELECT ?,tag_id,origin FROM room_tags WHERE room_id=?", (keep, dup))
    c.execute("DELETE FROM room_tags WHERE room_id=?", (dup,))
    k = c.execute("SELECT description,price_note,first_seen,last_seen FROM rooms WHERE id=?", (keep,)).fetchone()
    d = c.execute("SELECT description,price_note,first_seen,last_seen FROM rooms WHERE id=?", (dup,)).fetchone()
    if d:
        if not k["description"] and d["description"]: c.execute("UPDATE rooms SET description=? WHERE id=?", (d["description"], keep))
        if not k["price_note"] and d["price_note"]: c.execute("UPDATE rooms SET price_note=? WHERE id=?", (d["price_note"], keep))
        if d["first_seen"] and (not k["first_seen"] or d["first_seen"] < k["first_seen"]): c.execute("UPDATE rooms SET first_seen=? WHERE id=?", (d["first_seen"], keep))
        if d["last_seen"] and (not k["last_seen"] or d["last_seen"] > k["last_seen"]): c.execute("UPDATE rooms SET last_seen=? WHERE id=?", (d["last_seen"], keep))
    c.execute("DELETE FROM rooms WHERE id=?", (dup,))

def cmd_merge_rooms(a):
    c = conn()
    k = c.execute("SELECT id,name,studio_id FROM rooms WHERE id=?", (a.keep,)).fetchone()
    if not k: raise SystemExit(f"找不到 room #{a.keep}")
    for dup in a.dups:
        d = c.execute("SELECT id,name,studio_id FROM rooms WHERE id=?", (dup,)).fetchone()
        if not d: print(f"略過：找不到 room #{dup}"); continue
        if d["studio_id"] != k["studio_id"]: print(f"略過 #{dup}：不是同一家店"); continue
        print(f"併棚 #{dup} {d['name']} → #{k['id']} {k['name']}")
        _merge_room(c, k["id"], dup)
    c.commit(); _reindex(c)

def cmd_dedupe_photos(a):
    c = conn(); groups = {}
    for r in c.execute("SELECT id,studio_id,url,room_id,local_path FROM photos ORDER BY id").fetchall():
        groups.setdefault((r["studio_id"],) + photo_key(r["url"]), []).append(r)
    removed = files = 0
    for key, rows in groups.items():
        if len(rows) < 2: continue
        # 留：有本地檔的優先，其次 id 最小；不帶 query 的網址優先當代表
        rows.sort(key=lambda r: (0 if r["local_path"] else 1, 1 if "?" in r["url"] else 0, r["id"]))
        keep, dups = rows[0], rows[1:]
        room = keep["room_id"] or next((d["room_id"] for d in dups if d["room_id"]), None)
        clean_url = next((r["url"] for r in rows if "?" not in r["url"]), keep["url"])
        if not a.dry_run:
            c.execute("UPDATE photos SET room_id=?, url=? WHERE id=?", (room, clean_url, keep["id"]))
        for d in dups:
            print(f"  刪重複 #{d['id']} {d['url'][:90]}  (留 #{keep['id']})")
            if d["local_path"] and d["local_path"] != keep["local_path"]:
                p = os.path.join(DOCS, d["local_path"])
                if os.path.exists(p):
                    files += 1
                    if not a.dry_run: os.remove(p)
            if not a.dry_run: c.execute("DELETE FROM photos WHERE id=?", (d["id"],))
            removed += 1
    if not a.dry_run: c.commit()
    print(f"{'（試跑）' if a.dry_run else ''}刪除重複照片 {removed} 筆、webp 檔 {files} 個")

def cmd_reset_errors(a):
    c = conn()
    n = c.execute("UPDATE photos SET fetch_error=NULL WHERE fetch_error LIKE ?", (f"%{a.like}%",)).rowcount
    c.commit(); print(f"已清除 {n} 筆含「{a.like}」的下載錯誤，下次 fetch_photos.py 會重抓")

def _reindex(c):
    c.execute("DELETE FROM rooms_fts")
    for r in c.execute("""SELECT r.id,r.name,r.description,s.name,s.city,s.district,s.address,
        (SELECT group_concat(t.name,' ') FROM room_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.room_id=r.id)
        FROM rooms r JOIN studios s ON s.id=r.studio_id""").fetchall():
        c.execute("INSERT INTO rooms_fts(rowid,room,description,tags,studio,city,district,address) VALUES(?,?,?,?,?,?,?,?)",
                  (r[0], r[1] or "", r[2] or "", r[7] or "", r[3] or "", r[4] or "", r[5] or "", r[6] or ""))
    c.execute("DELETE FROM studios_fts")
    for r in c.execute("""SELECT s.id,s.name,s.aliases,s.city,s.district,s.address,s.features,
        (SELECT group_concat(t.name,' ') FROM studio_tags st JOIN tags t ON t.id=st.tag_id WHERE st.studio_id=s.id),
        (SELECT group_concat(rm.name,' ') FROM rooms rm WHERE rm.studio_id=s.id AND rm.status!='gone') FROM studios s""").fetchall():
        c.execute("INSERT INTO studios_fts(rowid,name,aliases,city,district,address,features,tags,scenes) VALUES(?,?,?,?,?,?,?,?,?)",
                  (r[0],) + tuple(x or "" for x in r[1:]))
    c.commit()

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = p.add_subparsers(dest="cmd", required=True)
s = sub.add_parser("merge"); s.add_argument("keep", type=int); s.add_argument("dups", type=int, nargs="+"); s.add_argument("--name"); s.set_defaults(f=cmd_merge)
s = sub.add_parser("merge-rooms"); s.add_argument("keep", type=int); s.add_argument("dups", type=int, nargs="+"); s.set_defaults(f=cmd_merge_rooms)
s = sub.add_parser("dedupe-photos"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_dedupe_photos)
s = sub.add_parser("reset-errors"); s.add_argument("--like", required=True); s.set_defaults(f=cmd_reset_errors)
a = p.parse_args(); a.f(a)
