#!/bin/bash
RELAY_FILE="/Users/sound/dao-analyst/data/live/relay_pending.txt"
SENT_FILE="/Users/sound/dao-analyst/data/live/relay_last_sent.txt"

[ ! -f "$RELAY_FILE" ] && exit 0
CURRENT=$(cat "$RELAY_FILE")
[ -z "$CURRENT" ] || [ "$CURRENT" = "无待发送通知" ] && exit 0
PREV=$(cat "$SENT_FILE" 2>/dev/null)
[ "$CURRENT" = "$PREV" ] && exit 0

NODE="/Applications/AutoClaw.app/Contents/Resources/node/darwin-arm64/node"
OPENCLAW="/Users/sound/Library/Application Support/autoclaw/embedded-gateway-runtime/0aa756dc7703af4d/gateway/openclaw/node_modules/.bin/openclaw"
MSG=$(head -c 800 "$RELAY_FILE")

# Push - remove 2>/dev/null to see errors in relay_cron.log
if "$NODE" "$OPENCLAW" agent --agent dao --channel openclaw-weixin --deliver --timeout 60 --message "$MSG" 2>&1; then
    cp "$RELAY_FILE" "$SENT_FILE"
    echo "[$(date '+%H:%M:%S')] ✅ 已推送"
else
    echo "[$(date '+%H:%M:%S')] ❌ 推送失败(exit:$?)"
fi
