# 攝影棚監控資料庫

- `studios.db` — SQLite 主資料庫（94 家起）。Mac 上可用 DB Browser for SQLite 直接開。
- `studio.py` — 查詢工具　- `record.py` — 排程寫入結果用　- `feed.py` — 新開棚比對　- `import_md.py` — 從 md 重新匯入

## 常用查詢
```bash
cd ~/PhotoProject/攝影棚分析/watch
export STUDIO_DB=~/PhotoProject/攝影棚分析/watch/studios.db

python3 studio.py status                 # 總覽：營業狀態統計、未讀異動
python3 studio.py changes --days 7       # 近 7 天異動（新造景/歇業/新開棚）
python3 studio.py changes --unseen --mark-seen
python3 studio.py new --days 30          # 新開的棚
python3 studio.py tags                   # 所有 tag
python3 studio.py tag 日式和風 --city 台北市
python3 studio.py search 教室            # 全文搜尋（店名/特色/地址/tag/造景）
python3 studio.py show 斗室              # 單店詳情：造景、來源、異動史
python3 studio.py tag-add 斗室 我想去    # 自己加 tag
```

## 資料表
studios（店家/狀態/輪掃組）、sources（來源網址）、scenes（造景，含首見日期與已撤標記）、
photos、tags + studio_tags、checks（每次檢查紀錄）、changes（異動事件）、
snapshots、runs（排程執行紀錄）、feed_seen（PONPAI 最新場地比對）、studios_fts（全文索引）。

## 注意
排程每天檢查 1/7 的店（7 天一輪）＋每天掃一次 PONPAI 最新場地找新開棚。
透過連線資料夾操作時，SQLite 檔案鎖在掛載點無法運作，需先 `cp` 到本機再操作、再 `cat` 回來。
