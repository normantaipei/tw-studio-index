工具說明與查詢指令請看專案根目錄的 README.md。

重點：
- 資料本體是 `data/*.jsonl`（進版控），`studios.db` 由 `build_db.py` 重建，不進版控。
- 改完資料庫後要 `python3 export_data.py` 再 commit，否則變更不會進版控。
- 透過 Claude 的連線資料夾操作時，SQLite 檔案鎖在掛載點無法運作：先 `cp` 到本機、操作完再寫回。
