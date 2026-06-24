#!/bin/bash
# DAO → 微信推送（2026-06-24 修复: cron环境注入OPENCLAW_BUNDLED_PLUGINS_DIR）
RELAY_FILE="$HOME/dao-analyst/data/live/relay_pending.txt"
SENT_FILE="$HOME/dao-analyst/data/live/relay_last_sent.txt"
LOG_FILE="$HOME/dao-analyst/logs/relay_cron.log"
WECHAT_TARGET="o9cq80wRoXDnZLK2e_Z4fWXMSNSs@im.wechat"
OPENCLAW="/Users/sound/.local/bin/openclaw"

# OpenClaw gateway env vars (needed for CLI in cron context)
export OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-$HOME/.openclaw-autoclaw}"
export OPENCLAW_CONFIG_PATH="${OPENCLAW_CONFIG_PATH:-$HOME/.openclaw-autoclaw/openclaw.runtime.json}"
export OPENCLAW_GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
export OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-30d72e76beea3aeaa8167d62b7e893c4be77a9631762a0eb64b347a6097163a9}"
export OPENCLAW_CLI=1
export OPENCLAW_DISABLE_BONJOUR=1
export NODE_NO_WARNINGS=1
export OPENCLAW_BUNDLED_PLUGINS_DIR="/Users/sound/Library/Application Support/autoclaw/embedded-gateway-runtime/f3b939065232a1fa/gateway/openclaw/extensions"

[ ! -f "$RELAY_FILE" ] && exit 0
CURRENT=$(cat "$RELAY_FILE")
[ -z "$CURRENT" ] || [ "$CURRENT" = "无待发送通知" ] && exit 0
PREV=$(cat "$SENT_FILE" 2>/dev/null)
[ "$CURRENT" = "$PREV" ] && exit 0

MSG=$(head -c 800 "$RELAY_FILE")
NOW=$(date '+%H:%M:%S')

if "$OPENCLAW" message send --channel openclaw-weixin --target "$WECHAT_TARGET" --message "$MSG" >/dev/null 2>&1; then
    cp "$RELAY_FILE" "$SENT_FILE"
    echo "[$NOW] ✅" >> "$LOG_FILE"
else
    echo "[$NOW] ❌ 微信推送失败" >> "$LOG_FILE"
fi
