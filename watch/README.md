工具說明與查詢指令請看專案根目錄的 README.md。

重點：
- 資料本體是 `data/*.jsonl`（進版控），`studios.db` 由 `build_db.py` 重建，不進版控。
- 改完資料庫後要 `python3 export_data.py` 再 commit，否則變更不會進版控。
- 透過 Claude 的連線資料夾操作時，SQLite 檔案鎖在掛載點無法運作：先 `cp` 到本機、操作完再寫回。

## 每日自動巡檢（本機 launchd 版）
- `daily_claude.sh`：一支做完 —— Claude Code 無人值守巡檢（提示詞在 `patrol_prompt.md`）→ 抓圖 → 重建網站 → 匯出 → commit → push。
- 機密放在 repo 外的 `~/.config/studiowatch/env`（`CLAUDE_CODE_OAUTH_TOKEN`，選填 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`）。
- 安裝：`cp watch/com.norman.studiowatch.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.norman.studiowatch.plist`
- 手動跑一次：`launchctl kickstart -k gui/$(id -u)/com.norman.studiowatch`，紀錄在 `watch/daily_claude.log`。
- `daily_mac.sh` 是舊的兩段式做法（搭配雲端排程）留下的，新流程不再使用。
