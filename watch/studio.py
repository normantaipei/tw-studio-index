#!/usr/bin/env python3
"""攝影棚資料庫工具（以「棚」為主體）

  python3 studio.py find 教室              # 搜尋棚（店名/棚名/描述/tag/地址）
  python3 studio.py tag 歐風 --city 台北市  # 依 tag 找棚
  python3 studio.py tags                   # 所有 tag 與棚數
  python3 studio.py show 斗室               # 一家店的所有棚 + 來源 + 異動史
  python3 studio.py studios --city 台中市    # 店家清單
  python3 studio.py changes --days 7        # 近期異動
  python3 studio.py new --days 30           # 新開的棚/新店
  python3 studio.py status                  # 總覽
  python3 studio.py tag-add --room 123 想拍  # 幫某個棚加 tag（room id 從 find 的 #號取得）
  python3 studio.py tag-add --studio 斗室 口袋名單
  python3 studio.py due                     # 今日輪掃名單（排程用，JSON）
  python3 studio.py reindex
"""
import argparse, json, os, sqlite3, datetime

DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
STATUS = {"closed":"❌已歇業","suspect_closed":"⚠️疑似歇業","moved":"📦已搬遷","open":"✅營業中","unknown":"・未確認"}

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

ROOM_SEL = """
SELECT r.id room_id, r.name room, r.description, r.price_note room_price, r.status room_status, r.period,
       r.first_seen, s.id studio_id, s.name studio, s.city, s.district, s.address, s.status studio_status,
       (SELECT group_concat(t.name,', ') FROM room_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.room_id=r.id) tags
FROM rooms r JOIN studios s ON s.id=r.studio_id"""

def show_room(r, with_studio=True):
    head = f'#{r["room_id"]} {r["room"]}'
    if r["room_status"] == "gone": head += "（已撤）"
    if r["room_status"] == "limited": head += f'（期間限定 {r["period"] or ""}）'
    print(head)
    if with_studio:
        print(f'    └ {r["studio"]}  [{r["city"] or ""}{r["district"] or ""}] {STATUS.get(r["studio_status"],"")}')
    if r["tags"]: print(f'    tags: {r["tags"]}')
    if r["description"]: print(f'    {r["description"][:110]}')
    if r["room_price"]: print(f'    價格: {r["room_price"]}')

def cmd_find(a):
    c = conn(); q = a.query
    ids = [x[0] for x in c.execute("SELECT rowid FROM rooms_fts WHERE rooms_fts MATCH ?", (q,))]
    if not ids:
        ids = [x[0] for x in c.execute("""SELECT r.id FROM rooms r JOIN studios s ON s.id=r.studio_id
               WHERE r.name LIKE ?1 OR r.description LIKE ?1 OR s.name LIKE ?1 OR s.address LIKE ?1""", ('%'+q+'%',))]
    if not ids: print("查無結果"); return
    sql = ROOM_SEL + f" WHERE r.id IN ({','.join('?'*len(ids))})"
    p = list(ids)
    if a.city: sql += " AND s.city LIKE ?"; p.append('%'+a.city+'%')
    if not a.include_closed: sql += " AND s.status != 'closed' AND r.status != 'gone'"
    rows = list(c.execute(sql + " ORDER BY s.city, s.name", p))
    for r in rows: show_room(r)
    print(f"\n共 {len(rows)} 個棚")

def cmd_tag(a):
    c = conn(); p = [a.name]
    sql = ROOM_SEL + " JOIN room_tags rt ON rt.room_id=r.id JOIN tags t ON t.id=rt.tag_id WHERE t.name=?"
    if a.city: sql += " AND s.city LIKE ?"; p.append('%'+a.city+'%')
    if not a.include_closed: sql += " AND s.status != 'closed' AND r.status != 'gone'"
    rows = list(c.execute(sql + " ORDER BY s.city, s.name", p))
    for r in rows: show_room(r)
    print(f"\n共 {len(rows)} 個棚，分布 {len(set(r['studio'] for r in rows))} 家店")

def cmd_tags(a):
    c = conn()
    for r in c.execute("""SELECT t.name, COUNT(*) n FROM tags t JOIN room_tags rt ON rt.tag_id=t.id
                          GROUP BY 1 ORDER BY n DESC"""):
        print(f'{r[0]:<10} {r[1]:>3} 棚')

def cmd_show(a):
    c = conn()
    s = c.execute("SELECT * FROM studios WHERE name LIKE ?", ('%'+a.name+'%',)).fetchone()
    if not s: print("查無此店"); return
    print(f'{s["name"]}  [{s["city"] or ""}{s["district"] or ""}] {STATUS.get(s["status"],"")}')
    if s["address"]: print(f'  地址: {s["address"]}')
    if s["price_note"]: print(f'  價格: {s["price_note"]}')
    if s["features"]: print(f'  特色: {s["features"][:200]}')
    print(f'  最後檢查: {s["last_checked"] or "未檢查"}｜輪掃組 {s["cohort"]}｜狀態備註: {s["status_note"] or "-"}')
    rows = list(c.execute(ROOM_SEL + " WHERE s.id=? ORDER BY r.status, r.name", (s["id"],)))
    print(f'  棚（{len(rows)}）:')
    for r in rows:
        tag = f' [{r["tags"]}]' if r["tags"] else ""
        mark = "（已撤）" if r["room_status"]=="gone" else ("（期間限定）" if r["room_status"]=="limited" else "")
        print(f'    #{r["room_id"]} {r["room"]}{mark}{tag}')
        if r["description"]: print(f'         {r["description"][:90]}')
    print("  來源:")
    for x in c.execute("SELECT kind,url,last_status FROM sources WHERE studio_id=?", (s["id"],)):
        print(f'    [{x["kind"]}] {x["url"]} {x["last_status"] or ""}')
    ch = list(c.execute("SELECT detected_at,type,summary FROM changes WHERE studio_id=? ORDER BY detected_at DESC LIMIT 10", (s["id"],)))
    if ch:
        print("  異動:")
        for x in ch: print(f'    {x["detected_at"][:10]} [{x["type"]}] {x["summary"]}')

def cmd_studios(a):
    c = conn(); p = []; sql = """SELECT s.*, (SELECT COUNT(*) FROM rooms r WHERE r.studio_id=s.id AND r.status!='gone') nrooms,
        (SELECT group_concat(t.name,', ') FROM studio_tags st JOIN tags t ON t.id=st.tag_id WHERE st.studio_id=s.id) tags
        FROM studios s WHERE 1=1"""
    if a.city: sql += " AND s.city LIKE ?"; p.append('%'+a.city+'%')
    if a.status: sql += " AND s.status=?"; p.append(a.status)
    rows = list(c.execute(sql + " ORDER BY s.city, s.district, s.name", p))
    for r in rows:
        print(f'#{r["id"]} {r["name"]}  [{r["city"] or ""}{r["district"] or ""}] {STATUS.get(r["status"],"")}  {r["nrooms"]} 棚')
        if r["tags"]: print(f'    {r["tags"]}')
    print(f"\n共 {len(rows)} 家")

def cmd_changes(a):
    c = conn(); q = "SELECT * FROM changes WHERE 1=1"; p = []
    if a.unseen: q += " AND seen=0"
    if a.days: q += " AND detected_at >= ?"; p.append((datetime.date.today()-datetime.timedelta(days=a.days)).isoformat())
    if a.type: q += " AND type=?"; p.append(a.type)
    rows = list(c.execute(q + " ORDER BY detected_at DESC", p))
    icon = {"new_studio":"🆕新開店","new_room":"🎬新棚","room_gone":"🚫棚已撤","closed":"❌歇業",
            "suspect_closed":"⚠️疑似歇業","reopened":"🔄恢復營業","moved":"📦搬遷","price":"💰價格",
            "renamed":"✏️改名","site_dead":"🔗官網失聯","source_found":"🔍新來源"}
    for r in rows:
        print(f'{r["detected_at"][:16]} {icon.get(r["type"], r["type"])} {r["studio_name"] or ""}｜{r["summary"]}')
        if r["detail"]: print(f'    {r["detail"][:200]}')
        if r["source_url"]: print(f'    {r["source_url"]}')
    print(f"\n共 {len(rows)} 筆")
    if a.mark_seen and rows:
        c.execute("UPDATE changes SET seen=1 WHERE id IN (%s)" % ",".join(str(r["id"]) for r in rows)); c.commit()
        print("（已標記為已讀）")

def cmd_new(a):
    a.unseen = False; a.mark_seen = False
    for t in ("new_studio", "new_room"):
        a.type = t; cmd_changes(a)

def cmd_status(a):
    c = conn(); g = lambda q, *p: c.execute(q, p).fetchone()[0]
    cnt = lambda st: g("SELECT COUNT(*) FROM studios WHERE status=?", st)
    print("資料庫:", DB)
    print("店家 %d（營業中 %d／疑似歇業 %d／已歇業 %d／未確認 %d）" %
          (g("SELECT COUNT(*) FROM studios"), cnt("open"), cnt("suspect_closed"), cnt("closed"), cnt("unknown")))
    print("棚 %d（現役 %d／已撤 %d）｜tag %d 種｜僅 FB/IG 來源 %d 家" %
          (g("SELECT COUNT(*) FROM rooms"), g("SELECT COUNT(*) FROM rooms WHERE status!='gone'"),
           g("SELECT COUNT(*) FROM rooms WHERE status='gone'"), g("SELECT COUNT(*) FROM tags"),
           g("SELECT COUNT(*) FROM studios WHERE fb_only=1")))
    print("未讀異動 %d｜近 7 天異動 %d" %
          (g("SELECT COUNT(*) FROM changes WHERE seen=0"),
           g("SELECT COUNT(*) FROM changes WHERE detected_at >= date('now','-7 day')")))
    print("最近排程執行:")
    for r in c.execute("SELECT ran_at,cohort,studios_checked,changes_found FROM runs ORDER BY id DESC LIMIT 3"):
        print(f'  {r["ran_at"]} 第{r["cohort"]}組 檢查{r["studios_checked"]}家 異動{r["changes_found"]}件')
    stale = [r["name"] for r in c.execute("SELECT name FROM studios WHERE last_checked IS NULL OR last_checked < date('now','-14 day') LIMIT 5")]
    if stale: print("超過 14 天未檢查:", ", ".join(stale), "…")

def cmd_due(a):
    c = conn()
    cohort = a.cohort if a.cohort is not None else datetime.date.today().toordinal() % 7
    out = []
    for r in c.execute("""SELECT id,name,city,district,address,status,fb_only,baseline_done,last_checked
                          FROM studios WHERE cohort=? AND status != 'closed' ORDER BY id""", (cohort,)):
        out.append(dict(
            id=r["id"], name=r["name"], city=r["city"], district=r["district"], address=r["address"],
            status=r["status"], fb_only=bool(r["fb_only"]), baseline_done=bool(r["baseline_done"]),
            last_checked=r["last_checked"],
            sources=[dict(kind=x["kind"], url=x["url"]) for x in
                     c.execute("SELECT kind,url FROM sources WHERE studio_id=? AND kind NOT IN ('fb','ig')", (r["id"],))],
            known_rooms=[x[0] for x in c.execute("SELECT name FROM rooms WHERE studio_id=? AND status!='gone'", (r["id"],))]))
    print(json.dumps({"cohort": cohort, "count": len(out), "studios": out}, ensure_ascii=False, indent=1))

def cmd_tag_add(a):
    c = conn()
    c.execute("INSERT OR IGNORE INTO tags(name,category) VALUES(?,?)", (a.tag, a.category))
    tid = c.execute("SELECT id FROM tags WHERE name=?", (a.tag,)).fetchone()[0]
    if a.room:
        c.execute("INSERT OR IGNORE INTO room_tags(room_id,tag_id,origin) VALUES(?,?,'manual')", (int(a.room), tid))
        print(f"已給棚 #{a.room} 加上 tag：{a.tag}")
    elif a.studio:
        s = c.execute("SELECT id,name FROM studios WHERE name LIKE ?", ('%'+a.studio+'%',)).fetchone()
        if not s: print("查無此店"); return
        c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) VALUES(?,?,'manual')", (s["id"], tid))
        print(f'已給 {s["name"]} 加上 tag：{a.tag}')
    else:
        print("請指定 --room <id> 或 --studio <店名>"); return
    c.commit(); cmd_reindex(a)

def cmd_reindex(a):
    c = conn()
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

p = argparse.ArgumentParser(description="攝影棚資料庫工具（以棚為主體）")
sub = p.add_subparsers(dest="cmd", required=True)
s = sub.add_parser("find", help="搜尋棚"); s.add_argument("query"); s.add_argument("--city"); s.add_argument("--include-closed", action="store_true"); s.set_defaults(f=cmd_find)
s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--city"); s.add_argument("--include-closed", action="store_true"); s.set_defaults(f=cmd_find)
s = sub.add_parser("tag"); s.add_argument("name"); s.add_argument("--city"); s.add_argument("--include-closed", action="store_true"); s.set_defaults(f=cmd_tag)
s = sub.add_parser("tags"); s.set_defaults(f=cmd_tags)
s = sub.add_parser("show"); s.add_argument("name"); s.set_defaults(f=cmd_show)
s = sub.add_parser("studios"); s.add_argument("--city"); s.add_argument("--status"); s.set_defaults(f=cmd_studios)
s = sub.add_parser("changes"); s.add_argument("--days", type=int, default=30); s.add_argument("--unseen", action="store_true"); s.add_argument("--mark-seen", action="store_true"); s.add_argument("--type"); s.set_defaults(f=cmd_changes)
s = sub.add_parser("new"); s.add_argument("--days", type=int, default=30); s.set_defaults(f=cmd_new)
s = sub.add_parser("status"); s.set_defaults(f=cmd_status)
s = sub.add_parser("due"); s.add_argument("--cohort", type=int); s.set_defaults(f=cmd_due)
s = sub.add_parser("tag-add"); s.add_argument("tag"); s.add_argument("--room"); s.add_argument("--studio"); s.add_argument("--category", default="style"); s.set_defaults(f=cmd_tag_add)
s = sub.add_parser("reindex"); s.set_defaults(f=cmd_reindex)
a = p.parse_args(); a.f(a)
