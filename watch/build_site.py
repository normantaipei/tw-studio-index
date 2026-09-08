#!/usr/bin/env python3
"""從 studios.db 產生公開查詢頁 docs/index.html 與 docs/data/*.json（GitHub Pages 用）。"""
import json, os, sqlite3, datetime, html

DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()

studios = {}
studios_by_key = {}
for s in c.execute("SELECT * FROM studios ORDER BY city, district, name").fetchall():
    studios[s["id"]] = dict(
        name=s["name"], city=s["city"] or "", district=s["district"] or "", address=s["address"] or "",
        features=s["features"] or "", price=s["price_note"] or "", status=s["status"] or "unknown",
        status_note=s["status_note"] or "", notes=s["notes"] or "", fb_only=bool(s["fb_only"]),
        last_checked=s["last_checked"] or "", sources=[], photos=[])
    studios_by_key[s["id"]] = studios[s["id"]]
for x in c.execute("SELECT studio_id,kind,url FROM sources ORDER BY is_primary DESC, id").fetchall():
    if x["studio_id"] in studios: studios[x["studio_id"]]["sources"].append({"kind": x["kind"], "url": x["url"]})
for x in c.execute("SELECT studio_id,url,local_path FROM photos ORDER BY id").fetchall():
    if x["studio_id"] in studios:
        studios[x["studio_id"]]["photos"].append({"u": x["url"], "p": x["local_path"] or None})

ORDER_CITY = ["台北市","新北市","桃園市","苗栗縣","彰化縣","台中市","台南市","高雄市","屏東縣","嘉義市"]
rooms = []
_rows = c.execute("SELECT r.*, s.id sid FROM rooms r JOIN studios s ON s.id=r.studio_id").fetchall()
_rows.sort(key=lambda x: (ORDER_CITY.index(studios[x["sid"]]["city"]) if studios[x["sid"]]["city"] in ORDER_CITY else 99,
                          studios[x["sid"]]["name"], x["name"]))
for r in _rows:
    st = studios[r["sid"]]
    rooms.append(dict(studio_key=r["sid"],
        id=r["id"], name=r["name"], desc=r["description"] or "", status=r["status"],
        period=r["period"] or "", price=r["price_note"] or "", studio=st["name"],
        city=st["city"], district=st["district"],
        tags=sorted(x[0] for x in c.execute(
            "SELECT t.name FROM room_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.room_id=?", (r["id"],)).fetchall()),
        photos=[{"u": x[0], "p": x[1] or None} for x in
                c.execute("SELECT url, local_path FROM photos WHERE room_id=? ORDER BY id", (r["id"],)).fetchall()]))

# 照片分配：每個棚最多一張，同店不重複。
# 1) 有 room_id 的照片 → 歸該棚，標 exact（確定是這個棚）
# 2) 剩下的店家照片 → 依序分給還沒有圖的棚，一棚一張，標 store（店家場景照，未必是此棚）
# 3) 分完就沒了：其餘棚不給圖，顯示佔位，不重複借用
by_studio = {}
for rm in rooms:
    by_studio.setdefault(rm["studio_key"], []).append(rm)
for skey, rms in by_studio.items():
    st = studios_by_key[skey]
    used = set()
    for rm in rms:
        if rm["photos"]:
            ph = rm["photos"][0]
            rm["photo"] = {"p": ph["p"], "u": ph["u"], "exact": True}
            used.add(ph["u"])
        else:
            rm["photo"] = None
    spare = [x for x in st["photos"] if x["u"] not in used]
    i = 0
    for rm in rms:
        if rm["photo"] is None and i < len(spare):
            rm["photo"] = {"p": spare[i]["p"], "u": spare[i]["u"], "exact": False}
            i += 1
for rm in rooms:
    rm.pop("photos", None); rm.pop("studio_key", None)

data = {"generated": datetime.date.today().isoformat(),
        "studios": list(studios.values()), "rooms": rooms}
# 讓 rooms 用索引指回 studio，縮小體積
idx = {s["name"]: i for i, s in enumerate(data["studios"])}
for rm in data["rooms"]:
    rm["s"] = idx[rm.pop("studio")]
    rm.pop("city"); rm.pop("district")

json.dump(data, open(os.path.join(DOCS, "data", "studios.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

tag_counts = {}
for rm in data["rooms"]:
    for t in rm["tags"]: tag_counts[t] = tag_counts.get(t, 0) + 1
cities = sorted({s["city"] for s in data["studios"] if s["city"]},
                key=lambda x: ["台北市","新北市","桃園市","苗栗縣","彰化縣","台中市","台南市","高雄市","屏東縣","嘉義市"].index(x)
                if x in ["台北市","新北市","桃園市","苗栗縣","彰化縣","台中市","台南市","高雄市","屏東縣","嘉義市"] else 99)

TPL = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "site_template.html"), encoding="utf-8").read()
out = (TPL.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
          .replace("__TAGS__", json.dumps(sorted(tag_counts.items(), key=lambda kv: -kv[1]), ensure_ascii=False))
          .replace("__CITIES__", json.dumps(cities, ensure_ascii=False))
          .replace("__GENERATED__", data["generated"])
          .replace("__NROOMS__", str(len(data["rooms"])))
          .replace("__NSTUDIOS__", str(len(data["studios"]))))
open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(out)
print(f'docs/index.html 產生完成：{len(data["rooms"])} 棚 / {len(data["studios"])} 家 / {len(tag_counts)} tag')
