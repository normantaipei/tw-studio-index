#!/usr/bin/env python3
# 把「攝影棚場景整理.md」匯入 studios.db（可重跑：以店名為 key upsert）
import re, sqlite3, sys, os, hashlib

MD = os.path.expanduser("~/mnt/攝影棚分析/攝影棚場景整理.md")
DB = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/studios.db")

TAGMAP = {
 "歐風": ["歐風","歐式","巴洛克","洛可可","南歐","教堂","城堡","古堡"],
 "日式和風": ["日式","和風","和室","榻榻米","昭和","神社","浴衣","祭典"],
 "中式古風": ["中式","中國風","古風","漢服","古典中","龍鳳"],
 "廢墟頹廢": ["廢墟","頹廢","監獄","牢房","地窖","水泥","鏽"],
 "白棚": ["白棚","白色背景","純白"],
 "黑棚": ["黑棚","全黑","純黑背景"],
 "教室校園": ["教室","校園","社團","課桌"],
 "床景居家": ["床景","居家","客廳","臥室","家景","浴室"],
 "書房": ["書房","圖書","書櫃"],
 "自然光": ["自然光","開窗","大窗"],
 "水景": ["水拍","泳池","水景","浴缸"],
 "電競直播": ["電競","直播"],
 "科技未來": ["科技","賽博","未來","RGB"],
 "蘿莉塔": ["蘿莉塔","lolita","Lolita"],
 "奇幻": ["奇幻","魔法","精靈","童話"],
 "復古老件": ["復古","古董","老件","老屋","懷舊"],
 "戶外實景": ["戶外","庭園","花園","海灘","沙灘"],
 "酒吧舞台": ["酒吧","舞台","Live","live house","宴會廳"],
 "醫療病床": ["病床","診療","醫院","手術"],
 "韓系": ["韓風","韓系"],
 "南洋": ["南洋","峇里","熱帶"],
 "Cosplay友善": ["Cosplay","cos","コス"],
 "自助棚": ["自助","密碼鎖","自拍"],
 "大空間": ["坪大","百坪","100坪","86坪","容納","可容"],
}

def tags_for(text):
    out = []
    for tag, kws in TAGMAP.items():
        if any(k in text for k in kws):
            out.append(tag)
    return out

def source_kind(label, url):
    l, u = label, url.lower()
    if "ponpai" in u: return "ponpai"
    if "instagram" in u: return "ig"
    if "facebook" in u: return "fb"
    if "threads" in u: return "threads"
    if "pixnet" in u or "blog" in u or "痞客" in l: return "blog"
    if "官網" in l: return "official"
    if "預約" in l or "tinybot" in u or "sites.google" in u: return "booking"
    if "google" in u and "maps" in u: return "gmap"
    return "other"

def main():
    raw = open(MD, encoding="utf-8").read()
    lines = raw.split("\n")
    city = None
    cur = None
    entries = []
    in_appendix = False
    for ln in lines:
        if ln.startswith("## "):
            title = ln[3:].strip()
            if title.startswith("附"):
                in_appendix = True
                continue
            city = title
            continue
        if in_appendix:
            continue
        if ln.startswith("### "):
            head = ln[4:].strip()
            fb_only = 1 if ("僅 FB" in head or "僅 IG" in head or "僅FB" in head or "幾乎僅 FB" in head) else 0
            head_clean = re.split(r"\s*—", head)[0].strip()
            m = re.match(r"^(.*?)\s*[（(]([^（()）]*)[)）]\s*$", head_clean)
            if m:
                name, district = m.group(1).strip(), m.group(2).strip()
            else:
                name, district = head_clean, ""
            cur = {"name": name, "district": district, "city": city, "fb_only": fb_only,
                   "features": "", "address": "", "photos": [], "sources": [], "notes": ""}
            entries.append(cur)
            continue
        if cur is None:
            continue
        s = ln.strip()
        if s.startswith("- **特色**"):
            cur["features"] = s.split("**:",1)[-1].split("**：",1)[-1].strip(": ：")
        elif s.startswith("- **地址**"):
            cur["address"] = s.split("**:",1)[-1].split("**：",1)[-1].strip(": ：")
        elif s.startswith("- **來源**"):
            body = s.split("**",2)[-1].lstrip(": ：")
            for part in re.split(r"[｜|]", body):
                urls = re.findall(r"https?://[^\s｜|)）,，]+", part)
                label = re.sub(r"https?://\S+", "", part).strip()
                for u in urls:
                    cur["sources"].append((source_kind(label, u), u.rstrip("。，,"), label))
        elif re.match(r"^-\s+https?://", s):
            cur["photos"].append(re.findall(r"https?://\S+", s)[0])
        elif s.startswith("- ") and not s.startswith("- **"):
            cur["notes"] += s[2:].strip() + " "
            for u in re.findall(r"https?://[^\s)）,，]+", s):
                cur["sources"].append((source_kind("", u), u, "備註"))

    con = sqlite3.connect(DB); c = con.cursor()
    for i, e in enumerate(entries):
        cohort = int(hashlib.md5(e["name"].encode()).hexdigest(), 16) % 7
        c.execute("""INSERT INTO studios(name,city,district,address,features,fb_only,cohort,notes)
                     VALUES(?,?,?,?,?,?,?,?)
                     ON CONFLICT(name) DO UPDATE SET city=excluded.city,district=excluded.district,
                       address=COALESCE(NULLIF(excluded.address,''),studios.address),
                       features=COALESCE(NULLIF(excluded.features,''),studios.features),
                       fb_only=excluded.fb_only, notes=excluded.notes""",
                  (e["name"], e["city"], e["district"], e["address"], e["features"],
                   e["fb_only"], cohort, e["notes"].strip()))
        sid = c.execute("SELECT id FROM studios WHERE name=?", (e["name"],)).fetchone()[0]
        for kind, url, label in e["sources"]:
            c.execute("INSERT OR IGNORE INTO sources(studio_id,kind,url,is_primary) VALUES(?,?,?,?)",
                      (sid, kind, url, 1 if kind in ("official","booking") else 0))
        for u in e["photos"]:
            c.execute("INSERT OR IGNORE INTO photos(studio_id,url) VALUES(?,?)", (sid, u))
        for t in tags_for(e["features"] + " " + e["notes"]):
            c.execute("INSERT OR IGNORE INTO tags(name,category) VALUES(?,'style')", (t,))
            tid = c.execute("SELECT id FROM tags WHERE name=?", (t,)).fetchone()[0]
            c.execute("INSERT OR IGNORE INTO studio_tags(studio_id,tag_id,origin) VALUES(?,?,'auto')", (sid, tid))
    con.commit()

    # 重建全文索引
    c.execute("DELETE FROM studios_fts")
    for row in c.execute("""SELECT s.id,s.name,s.aliases,s.city,s.district,s.address,s.features,
             (SELECT group_concat(t.name,' ') FROM studio_tags st JOIN tags t ON t.id=st.tag_id WHERE st.studio_id=s.id),
             (SELECT group_concat(sc.name,' ') FROM scenes sc WHERE sc.studio_id=s.id)
             FROM studios s""").fetchall():
        c.execute("INSERT INTO studios_fts(rowid,name,aliases,city,district,address,features,tags,scenes) VALUES(?,?,?,?,?,?,?,?,?)",
                  (row[0],) + tuple(x or "" for x in row[1:]))
    con.commit()
    print(f"匯入 {len(entries)} 家店")
    for q, label in [("SELECT COUNT(*) FROM studios","studios"),("SELECT COUNT(*) FROM sources","sources"),
                     ("SELECT COUNT(*) FROM photos","photos"),("SELECT COUNT(*) FROM tags","tags"),
                     ("SELECT COUNT(*) FROM studio_tags","studio_tags"),("SELECT COUNT(*) FROM studios WHERE fb_only=1","fb_only")]:
        print(label, c.execute(q).fetchone()[0])

main()
