#!/bin/bash
# DAO → 微信推送 (2026-06-27 最终版)
set -e

# 周末跳过
[ $(date +%u) -ge 6 ] && exit 0

RELAY_FILE="$HOME/dao-analyst/data/live/relay_pending.txt"
SENT_FILE="$HOME/dao-analyst/data/live/relay_last_sent.txt"
LOG_FILE="$HOME/dao-analyst/logs/relay_cron.log"
WECHAT_TARGET="o9cq80wRoXDnZLK2e_Z4fWXMSNSs@im.wechat"
CLI="$HOME/.local/bin/openclaw"

[ ! -f "$RELAY_FILE" ] && exit 0
CURRENT=$(cat "$RELAY_FILE")
[ -z "$CURRENT" ] || [ "$CURRENT" = "无待发送通知" ] && exit 0
PREV=$(cat "$SENT_FILE" 2>/dev/null)
[ "$CURRENT" = "$PREV" ] && exit 0

MSG=$(head -c 800 "$RELAY_FILE")
NOW=$(date '+%H:%M:%S')

if "$CLI" message send --channel openclaw-weixin --target "$WECHAT_TARGET" --message "$MSG" >/dev/null 2>&1; then
    cp "$RELAY_FILE" "$SENT_FILE"
    echo "[$NOW] ✅" >> "$LOG_FILE"
else
    echo "[$NOW] ❌" >> "$LOG_FILE"
fi
