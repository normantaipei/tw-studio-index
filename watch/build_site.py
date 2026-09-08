#!/usr/bin/env python3
"""從 studios.db 產生公開查詢頁 docs/index.html 與 docs/data/*.json（GitHub Pages 用）。"""
import json, os, sqlite3, datetime, html

DB = os.environ.get("STUDIO_DB", os.path.expanduser("~/studios.db"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()

studios = {}
for s in c.execute("SELECT * FROM studios ORDER BY city, district, name").fetchall():
    studios[s["id"]] = dict(
        name=s["name"], city=s["city"] or "", district=s["district"] or "", address=s["address"] or "",
        features=s["features"] or "", price=s["price_note"] or "", status=s["status"] or "unknown",
        status_note=s["status_note"] or "", notes=s["notes"] or "", fb_only=bool(s["fb_only"]),
        last_checked=s["last_checked"] or "", sources=[], photos=[])
for x in c.execute("SELECT studio_id,kind,url FROM sources ORDER BY is_primary DESC, id").fetchall():
    if x["studio_id"] in studios: studios[x["studio_id"]]["sources"].append({"kind": x["kind"], "url": x["url"]})
for x in c.execute("SELECT studio_id,url FROM photos ORDER BY id").fetchall():
    if x["studio_id"] in studios: studios[x["studio_id"]]["photos"].append(x["url"])

ORDER_CITY = ["台北市","新北市","桃園市","苗栗縣","彰化縣","台中市","台南市","高雄市","屏東縣","嘉義市"]
rooms = []
_rows = c.execute("SELECT r.*, s.id sid FROM rooms r JOIN studios s ON s.id=r.studio_id").fetchall()
_rows.sort(key=lambda x: (ORDER_CITY.index(studios[x["sid"]]["city"]) if studios[x["sid"]]["city"] in ORDER_CITY else 99,
                          studios[x["sid"]]["name"], x["name"]))
for r in _rows:
    st = studios[r["sid"]]
    rooms.append(dict(
        id=r["id"], name=r["name"], desc=r["description"] or "", status=r["status"],
        period=r["period"] or "", price=r["price_note"] or "", studio=st["name"],
        city=st["city"], district=st["district"],
        tags=sorted(x[0] for x in c.execute(
            "SELECT t.name FROM room_tags rt JOIN tags t ON t.id=rt.tag_id WHERE rt.room_id=?", (r["id"],)).fetchall())))

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
