#!/bin/bash
# 攝影棚每日巡檢（本機 launchd 版，一支做完）：
#   Claude Code 無人值守巡檢並寫進資料庫 → 抓新圖壓 webp → 重建網站 → 匯出 jsonl → commit → push
# 取代原本「雲端排程巡檢 + daily_mac.sh 收尾」的兩段式做法。
#
# 機密不放在這個公開 repo。請自行建立 ~/.config/studiowatch/env（chmod 600），內容：
#   CLAUDE_CODE_OAUTH_TOKEN=...      # claude setup-token 產生的長效 token
#   TELEGRAM_BOT_TOKEN=...           # 選填：有填才會發 Telegram
#   TELEGRAM_CHAT_ID=...             # 選填
set -uo pipefail

REPO="$HOME/PhotoProject/攝影棚分析"
ENVF="$HOME/.config/studiowatch/env"
RUN="$REPO/watch/.run"
LOG="$REPO/watch/daily_claude.log"
TIMEOUT_SEC=3000                     # Claude 最長跑 50 分鐘
export STUDIO_DB="$REPO/watch/studios.db"
export PATH="$HOME/.local/bin:$HOME/.claude/local:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

mkdir -p "$RUN"
exec >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 開始 ====="

if [ -f "$ENVF" ]; then set -a; . "$ENVF"; set +a; else echo "找不到 $ENVF（沒有 token 與 Telegram 設定）"; fi

notify() {   # notify "訊息"：有 Telegram 設定就發 Telegram，否則跳 macOS 通知
  local msg; msg="$(printf '%s' "$1" | python3 -c 'import sys; print(sys.stdin.read()[:3500])')"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -sS -m 20 -o /dev/null "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=${msg}" \
      --data-urlencode "disable_web_page_preview=true" || echo "Telegram 發送失敗"
  else
    osascript -e 'display notification "詳見 watch/daily_claude.log" with title "攝影棚巡檢" subtitle "'"$(printf '%s' "$1" | head -1 | tr -d '"\\' | cut -c1-80)"'"' 2>/dev/null || true
  fi
}

checks_today() {   # 今天寫進 checks 表的筆數，用來判斷巡檢是否真的有做事
  python3 - <<'PY'
import os, sqlite3, datetime
try:
    c = sqlite3.connect(os.environ["STUDIO_DB"])
    print(c.execute("SELECT COUNT(*) FROM checks WHERE checked_at LIKE ?", (datetime.date.today().isoformat() + "%",)).fetchone()[0])
except Exception:
    print(0)
PY
}

cd "$REPO" || { echo "找不到 repo"; notify "⚠️ 攝影棚巡檢失敗：找不到 $REPO"; exit 1; }

# 同一時間只跑一個
if ! mkdir "$RUN/lock" 2>/dev/null; then echo "已有另一個巡檢在跑，略過"; exit 0; fi
trap 'rmdir "$RUN/lock" 2>/dev/null' EXIT

PROBLEMS=""

# 0. 跟上遠端；資料庫不在就從 jsonl 重建
git pull -q --ff-only origin main || PROBLEMS="${PROBLEMS}git pull 失敗（可能與遠端分岔）；"
if [ ! -f "$STUDIO_DB" ]; then
  echo "studios.db 不存在，從 watch/data 重建"
  python3 watch/build_db.py "$STUDIO_DB" || { notify "⚠️ 攝影棚巡檢失敗：資料庫重建失敗"; exit 1; }
fi

# 1. Claude 巡檢（只查證與寫資料庫，不碰 git、不下載）
CLAUDE_BIN="$(command -v claude || true)"
BEFORE="$(checks_today)"
RC=127
if [ -z "$CLAUDE_BIN" ]; then
  echo "找不到 claude 指令（PATH=$PATH）"
else
  rm -f "$RUN/result.json" "$RUN/feed_in.json"
  "$CLAUDE_BIN" -p "$(cat watch/patrol_prompt.md)" > "$RUN/claude_out.txt" 2>&1 &
  CPID=$!
  ( sleep "$TIMEOUT_SEC"; echo "逾時，中止 Claude"; kill "$CPID" 2>/dev/null ) &
  WPID=$!
  wait "$CPID"; RC=$?
  pkill -P "$WPID" 2>/dev/null; kill "$WPID" 2>/dev/null
  cat "$RUN/claude_out.txt"; echo
fi
AFTER="$(checks_today)"
CHECKED=$((AFTER - BEFORE))
echo "Claude 結束碼 $RC，本輪寫入檢查 $CHECKED 筆"
if [ "$RC" -ne 0 ] || [ "$CHECKED" -le 0 ]; then
  PROBLEMS="${PROBLEMS}巡檢沒有完成（結束碼 $RC、寫入 $CHECKED 筆）：$(tail -c 300 "$RUN/claude_out.txt" 2>/dev/null | tr '\n' ' ')；"
fi

# 2. 抓新圖並壓成 640px webp（Google 地圖照片會自動跳過）、重建網站、匯出資料
python3 watch/fetch_photos.py --limit 120 || PROBLEMS="${PROBLEMS}fetch_photos 失敗；"
python3 watch/build_site.py   || PROBLEMS="${PROBLEMS}build_site 失敗；"
python3 watch/export_data.py  || PROBLEMS="${PROBLEMS}export_data 失敗；"

# 3. commit + push
if [ -n "$(git status --porcelain)" ]; then
  GITID=()
  if [ -z "$(git config user.email || true)" ]; then
    GITID=(-c "user.name=$(git log -1 --format=%an)" -c "user.email=$(git log -1 --format=%ae)")
  fi
  git add -A
  if git ${GITID[@]+"${GITID[@]}"} commit -q -m "巡檢 $(date '+%Y-%m-%d')：檢查 $CHECKED 家"; then
    if git push -q origin main; then echo "push 成功"; else PROBLEMS="${PROBLEMS}git push 失敗（檢查這台的 GitHub 憑證）；"; fi
  else
    PROBLEMS="${PROBLEMS}git commit 失敗；"
  fi
else
  echo "沒有變更"
fi

# 4. 回報
SUMMARY="$(python3 watch/studio.py changes --days 1 2>/dev/null | head -60)"
if [ -n "$PROBLEMS" ]; then
  echo "問題：$PROBLEMS"
  notify "⚠️ 攝影棚巡檢 $(date '+%m/%d') 有問題：
$PROBLEMS"
else
  notify "📷 攝影棚巡檢 $(date '+%m/%d')：檢查 $CHECKED 家
${SUMMARY:-無異動}"
fi
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 結束 ====="
[ -z "$PROBLEMS" ]
