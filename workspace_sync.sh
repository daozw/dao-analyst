#!/bin/bash
# 自动同步: 全部代码变更 → commit+push
REPO_DIR="/Users/sound/dao-analyst"

cd "$REPO_DIR"
git add -A 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "auto: $(date '+%Y-%m-%d %H:%M')"
    git push origin main 2>&1 | tail -1
    echo "[$(date '+%H:%M')] ✅ 已同步"
else
    echo "[$(date '+%H:%M')] 无变更"
fi
