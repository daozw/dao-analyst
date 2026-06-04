#!/bin/bash
# 自动同步到后台 — 每次系统更新后运行
cd /Users/sound/dao-analyst
git add -A 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
    git commit -m "auto: 系统更新 $TIMESTAMP" --allow-empty 2>/dev/null
    echo "✅ 已提交: $(date '+%H:%M')"
else
    echo "  (无变更)"
fi

# Push to remote if configured
REMOTE=$(git remote get-url origin 2>/dev/null)
if [ -n "$REMOTE" ]; then
    git push origin main 2>&1 | tail -1
fi
