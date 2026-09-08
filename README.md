# 攝影棚分析

全台攝影棚（以 Cosplay / 主題實景棚為主）的場景資料庫與每日監控。
**以「棚」為主體**：一家店有三個不同風格的棚，就是三筆資料，各自帶自己的 tag。

## 內容
```
攝影棚場景整理.md      原始整理（人工彙整，資料來源）
攝影棚場景相簿.html     場景照相簿
北部棚景印樣.html       北部棚景印樣
watch/
  data/*.jsonl        ★ 版控中的資料本體（studios / rooms / tags / changes / feed_seen）
  schema.sql
  schema_rooms.sql    棚、棚標籤、全文索引
  build_db.py         data/*.jsonl → studios.db（clone 後跑這支）
  export_data.py      studios.db → data/*.jsonl（改完資料後跑這支再 commit）
  studio.py           查詢工具
  record.py           每日排程寫入檢查結果
  feed.py             PONPAI 最新場地比對（找新開的棚）
  import_md.py        從 markdown 重新匯入（初次建庫用）
  migrate_rooms.py    scenes → rooms 結構遷移（已執行過）
```

## 起手式
```bash
cd watch
python3 build_db.py ./studios.db          # 重建資料庫
export STUDIO_DB=$PWD/studios.db
python3 studio.py status
```

## 查詢
```bash
python3 studio.py find 教室               # 搜尋棚（棚名/描述/tag/店名/地址）
python3 studio.py tag 廢墟頹廢 --city 台北市
python3 studio.py tags                    # 全部 tag 與棚數
python3 studio.py show 斗室                # 一家店的所有棚
python3 studio.py studios --city 台中市
python3 studio.py changes --days 7        # 近期異動
python3 studio.py new --days 30           # 新開的棚 / 新棚別
python3 studio.py tag-add 想拍 --room 102  # 幫某個棚加自己的 tag
```

## 每日監控
排程「攝影棚每日巡檢」每天早上 10:00 執行：
輪掃當天 1/7 的店家（7 天一輪）→ 官網比對棚別清單、Google 地圖確認營業狀態 →
掃 PONPAI「最新攝影場地」找新開的棚 → 寫進 `changes` 表 → 有異動才推播。

改完資料要進版控：
```bash
python3 export_data.py && git add -A && git commit -m "update: 2026-09-08 巡檢"
```

## 資料表
`studios`（店家/地址/營業狀態/輪掃組）、`rooms`（棚，主體）、`room_tags`、`tags`、
`sources`（來源網址）、`photos`、`checks`（每次檢查）、`changes`（異動事件）、
`runs`（排程紀錄）、`feed_seen`、`rooms_fts` / `studios_fts`（trigram 全文索引）。

## 注意
- 資料來自公開來源（官網、預約平台、PONPAI、Google 地圖），僅供拍攝場地參考；營業狀態以店家公告為準。
- 透過 Claude 的連線資料夾操作時，SQLite 檔案鎖在掛載點無法運作，需 `cp` 到本機再操作。
