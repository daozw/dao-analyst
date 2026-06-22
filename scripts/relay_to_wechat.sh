#!/bin/bash
# 双轨推送: crontab自动保底 + session手动主力
RELAY_FILE="$HOME/dao-analyst/data/live/relay_pending.txt"
SENT_FILE="$HOME/dao-analyst/data/live/relay_last_sent.txt"
CONFIG_FILE="$HOME/.openclaw-autoclaw/openclaw.runtime.json"
LOG_FILE="$HOME/dao-analyst/logs/relay_cron.log"

[ ! -f "$RELAY_FILE" ] && exit 0
CURRENT=$(cat "$RELAY_FILE")
[ -z "$CURRENT" ] || [ "$CURRENT" = "无待发送通知" ] && exit 0
PREV=$(cat "$SENT_FILE" 2>/dev/null)
[ "$CURRENT" = "$PREV" ] && exit 0

NODE="/Applications/AutoClaw.app/Contents/Resources/node/darwin-arm64/node"
CLI="$HOME/Library/Application Support/autoclaw/embedded-gateway-runtime/0aa756dc7703af4d/gateway/openclaw/node_modules/.bin/openclaw"
MSG=$(head -c 800 "$RELAY_FILE")

# 1. 修复Gateway反复重置的config
python3 -c "
import json
d=json.load(open('$CONFIG_FILE'))
d['channels'].get('feishu',{}).pop('name',None)
d.get('plugins',{}).pop('allow',None)
json.dump(d,open('$CONFIG_FILE','w'),indent=2)
" 2>/dev/null

# 2. 推送
NOW=$(date '+%H:%M:%S')
if "$NODE" "$CLI" agent --agent dao --channel weixin --deliver --timeout 30 --message "$MSG" >/dev/null 2>&1; then
    cp "$RELAY_FILE" "$SENT_FILE"
    echo "[$NOW] ✅" >> "$LOG_FILE"
else
    echo "[$NOW] ❌ CLI失败(session手动保底)" >> "$LOG_FILE"
fi
