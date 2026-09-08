#!/usr/bin/env python3
"""在「有網路的機器」（你的 Mac）上把 photos 表裡還沒本地化的圖抓下來，
壓成 640px 長邊的 WebP 存到 docs/img/，並把路徑寫回資料庫。

用法：
  cd ~/PhotoProject/攝影棚分析/watch
  STUDIO_DB=$PWD/studios.db python3 fetch_photos.py            # 只抓還沒抓過的
  STUDIO_DB=$PWD/studios.db python3 fetch_photos.py --limit 50 # 一次只抓 50 張
  STUDIO_DB=$PWD/studios.db python3 fetch_photos.py --retry    # 連之前失敗的也重試

不會下載 Google 地圖（lh3.googleusercontent.com）的照片 —— 那些屬於個別上傳者、
且 Google 服務條款不允許轉存，網站上維持外連。
"""
import argparse, hashlib, os, re, shutil, sqlite3, subprocess, sys, tempfile, urllib.request

MAXPX, QUALITY = 640, 72          # 卡片顯示約 300px 寬，兩倍給 retina
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMGDIR = os.path.join(ROOT, "docs", "img")
DB = os.environ.get("STUDIO_DB", os.path.join(HERE, "studios.db"))
SKIP_HOSTS = ("googleusercontent.com",)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

def slug(name):
    s = re.sub(r"[^\w一-鿿-]+", "-", name).strip("-")
    return s[:40] or hashlib.md5(name.encode()).hexdigest()[:8]

def have(cmd):
    return shutil.which(cmd) is not None

def convert(src, dst):
    """把 src 轉成 640px 長邊的 webp。依序嘗試 sips(macOS) / cwebp / Pillow。"""
    if have("sips"):
        r = subprocess.run(["sips", "-s", "format", "webp", "-s", "formatOptions", str(QUALITY),
                            "-Z", str(MAXPX), src, "--out", dst],
                           capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
            return "sips"
    if have("cwebp"):
        r = subprocess.run(["cwebp", "-quiet", "-q", str(QUALITY), "-resize", str(MAXPX), "0", src, "-o", dst],
                           capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 0:
            return "cwebp"
    try:
        from PIL import Image
        im = Image.open(src)
        im.thumbnail((MAXPX, MAXPX))
        if im.mode in ("P", "RGBA", "LA"):
            im = im.convert("RGB")
        im.save(dst, "WEBP", quality=QUALITY, method=5)
        return "pillow"
    except Exception as e:
        raise RuntimeError(f"沒有可用的轉檔工具或轉檔失敗：{e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retry", action="store_true", help="連先前失敗的一起重試")
    a = ap.parse_args()

    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row; c = con.cursor()
    q = """SELECT p.id, p.url, p.studio_id, s.name studio FROM photos p JOIN studios s ON s.id=p.studio_id
           WHERE (p.local_path IS NULL OR p.local_path='')"""
    if not a.retry:
        q += " AND (p.fetch_error IS NULL OR p.fetch_error='')"
    rows = [r for r in c.execute(q).fetchall() if not any(h in r["url"] for h in SKIP_HOSTS)]
    if a.limit: rows = rows[:a.limit]
    if not rows:
        print("沒有需要下載的圖片。"); return

    print(f"要處理 {len(rows)} 張…")
    ok = fail = 0
    for i, r in enumerate(rows, 1):
        d = os.path.join(IMGDIR, slug(r["studio"]))
        os.makedirs(d, exist_ok=True)
        name = hashlib.sha1(r["url"].encode()).hexdigest()[:12] + ".webp"
        dst = os.path.join(d, name)
        rel = os.path.relpath(dst, os.path.join(ROOT, "docs"))
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            c.execute("UPDATE photos SET local_path=?, fetch_error=NULL, fetched_at=date('now','localtime') WHERE id=?", (rel, r["id"]))
            con.commit(); ok += 1; continue
        try:
            req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = resp.read()
            if len(data) < 2000:
                raise RuntimeError("檔案太小，可能不是圖片")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as tf:
                tf.write(data); tmp = tf.name
            convert(tmp, dst)
            os.unlink(tmp)
            c.execute("UPDATE photos SET local_path=?, fetch_error=NULL, fetched_at=date('now','localtime') WHERE id=?", (rel, r["id"]))
            ok += 1
            print(f"  [{i}/{len(rows)}] {r['studio']} → {rel} ({os.path.getsize(dst)//1024}KB)")
        except Exception as e:
            c.execute("UPDATE photos SET fetch_error=? WHERE id=?", (str(e)[:200], r["id"]))
            fail += 1
            print(f"  [{i}/{len(rows)}] ✗ {r['studio']}：{str(e)[:80]}")
        con.commit()
    total = c.execute("SELECT COUNT(*) FROM photos WHERE local_path IS NOT NULL").fetchone()[0]
    print(f"\n完成：成功 {ok}、失敗 {fail}｜資料庫中已本地化 {total} 張")
    size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(IMGDIR) for f in fs)
    print(f"docs/img 目前 {size/1024/1024:.1f} MB")

main()
