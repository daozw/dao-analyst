#!/bin/bash
# 自动同步: 监听AGENTS.md/TOOLS.md/SOUL.md变更 → commit+push
WATCH_DIR="/Users/sound/.openclaw-autoclaw/agents/dao/workspace"
REPO_DIR="/Users/sound/dao-analyst"

# Copy workspace files to repo
cp "$WATCH_DIR"/AGENTS.md "$REPO_DIR/workspace/" 2>/dev/null
cp "$WATCH_DIR"/TOOLS.md "$REPO_DIR/workspace/" 2>/dev/null
cp "$WATCH_DIR"/SOUL.md "$REPO_DIR/workspace/" 2>/dev/null
cp "$WATCH_DIR"/MEMORY.md "$REPO_DIR/workspace/" 2>/dev/null

cd "$REPO_DIR"
git add workspace/ data/watchlist.json 2>/dev/null
if ! git diff --cached --quiet 2>/dev/null; then
    git commit -m "sync: workspace $(date '+%Y-%m-%d %H:%M')"
    git push origin main 2>&1 | tail -1
    echo "✅ 已同步"
else
    echo "  无变更"
fi
