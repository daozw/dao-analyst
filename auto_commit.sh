#!/bin/bash
cd /Users/sound/dao-analyst
git add -A 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "auto: $(date '+%Y-%m-%d %H:%M')" --allow-empty 2>/dev/null
    git push origin main 2>&1 | tail -1
    echo "✅ 已同步 $(date '+%H:%M')"
else
    echo "  (无变更)"
fi
