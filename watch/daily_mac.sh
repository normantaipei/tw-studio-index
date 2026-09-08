#!/bin/bash
# 在 Norman 的 Mac 上每天跑：抓新圖 → 壓成 webp → 重建網站 → commit → push
# 排程那台（雲端）連不到圖床、也沒有 GitHub 憑證，所以這段只能在本機做。
set -uo pipefail

REPO="$HOME/PhotoProject/攝影棚分析"
export STUDIO_DB="$REPO/watch/studios.db"
LOG="$REPO/watch/daily_mac.log"
exec >> "$LOG" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') 開始 ====="

cd "$REPO" || { echo "找不到 repo"; exit 1; }
[ -f "$STUDIO_DB" ] || { echo "找不到 studios.db，可能雲端排程還沒跑完"; exit 1; }

# 1. 抓新圖並壓成 640px webp（只處理還沒本地化的，Google 地圖照片會自動跳過）
python3 watch/fetch_photos.py --limit 120

# 2. 重建網站與匯出資料
python3 watch/build_site.py
python3 watch/export_data.py

# 3. commit + push（用你自己的 SSH 金鑰）
if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "每日更新 $(date '+%Y-%m-%d')：圖片與資料"
  rm -f .git/index.lock 2>/dev/null
  if git push origin main; then
    echo "push 成功"
  else
    echo "push 失敗（檢查 ssh -T git@github-personal）"
  fi
else
  echo "沒有變更"
fi
echo "===== 結束 ====="
