# 台灣攝影棚棚景索引 tw-studio-index

**[→ 線上查詢頁](https://normantaipei.github.io/tw-studio-index/)**

台灣 94 家攝影棚、363 個棚景的公開索引，給 cosplay 與人像攝影找場地用。

跟一般的攝影棚清單不一樣的地方：**這裡以「棚」為單位**。一家店裡的歐風房、白棚、廢墟區各自是一筆資料、各自標風格標籤，所以你可以直接搜「歐風 + 床景居家」找歐式床景，而不是先找到店、再自己翻它有沒有你要的景。

- 363 個棚、43 種風格／場景標籤（歐風、日式和風、廢墟頹廢、教室校園、水景、監獄、宮廷、梳化間…）
- 每家店附官網／預約平台／PONPAI／Google 地圖連結
- 排程每天輪流複查 1/7 的店，追蹤歇業、新棚上線、期間限定檔期、地址與價格變動，紀錄在 `changes` 裡

## 直接用資料

```bash
git clone https://github.com/normantaipei/tw-studio-index.git
cd tw-studio-index/watch
python3 build_db.py ./studios.db          # 從 JSONL 重建 SQLite（只需要 python3，無外部套件）
export STUDIO_DB=$PWD/studios.db

python3 studio.py find 榻榻米              # 搜尋棚（棚名／描述／tag／店名／地址）
python3 studio.py tag 廢墟頹廢 --city 台北市
python3 studio.py tags                    # 全部標籤與棚數
python3 studio.py show 斗室                # 一家店的所有棚
python3 studio.py changes --days 30       # 近期異動
```

也可以完全不碰 SQLite，直接讀這兩份：

| 檔案 | 內容 |
|---|---|
| `watch/data/rooms.jsonl` | 一行一個棚：棚名、描述、標籤、所屬店家、狀態 |
| `watch/data/studios.jsonl` | 一行一家店：地址、營業狀態、來源網址、場景照網址 |
| `watch/data/changes.jsonl` | 異動紀錄：新棚、撤景、歇業、搬遷、價格變動 |
| `docs/data/studios.json` | 查詢頁用的合併版（店家 + 棚 + 標籤） |

## 圖片

`docs/img/` 下是各攝影棚官網／PONPAI 場景照的**縮圖快取**（長邊 640px、WebP q72，約為網頁顯示尺寸的兩倍），
用途是讓這個索引頁能穩定顯示、不消耗各店伺服器頻寬。**這些照片的著作權屬於各攝影棚，不在本專案的授權範圍內**，
每張圖的圖說都連回原始來源。Google 地圖上的商家照片屬於個別上傳者，本專案不轉存，一律維持外連。

**店家若不希望自家照片出現在這裡**，開一則 issue 或來信告知，我會立即移除。

## 資料來源與準確度

彙整自各棚官網、線上預約平台、[PONPAI 攝影棚情報站](https://ponpai.tw/)與 Google 地圖等公開來源。標「僅 FB／IG」的店只在社群露出，需自行私訊。

**營業狀態、價格與造景以各店最新公告為準，出發前請自行確認。** 標籤與部分棚名是從公開描述整理的，可能與店家自己的稱呼不同。

## 回報與修正

發現資料錯誤、店家已歇業、有新棚或新開的店，[開一則 issue](https://github.com/normantaipei/tw-studio-index/issues) 告訴我。

**店家本人**若不希望自家資料出現在這裡，或要求修正內容，開 issue 或來信即可，我會盡快處理。場景照為直接引用各店官網／PONPAI 圖庫的原始網址，版權屬原攝影棚所有，僅作辨識用途。

## 授權

- 資料（`watch/data/`、`docs/data/`）：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh-hant) — 取用請註明出處
- 程式碼：MIT
- **圖片（`docs/img/`）不適用上述授權**：著作權屬各攝影棚，僅作索引辨識用途，請勿另作商業使用

## 專案結構

```
docs/                 GitHub Pages 查詢頁（index.html 為單檔，資料內嵌）
watch/
  data/*.jsonl        資料本體（版控的來源，SQLite 由此重建）
  build_db.py         JSONL → studios.db
  export_data.py      studios.db → JSONL
  build_site.py       studios.db → docs/
  studio.py           查詢工具
  record.py           每日巡檢寫入結果
  feed.py             新開棚比對
  schema.sql / schema_rooms.sql
攝影棚場景整理.md       最初的人工彙整（資料起點）
```
