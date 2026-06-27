#!/bin/bash
# 读取relay文件推送到微信
RELAY_FILE="/Users/sound/dao-analyst/data/live/relay_pending.txt"
SENT_FILE="/Users/sound/dao-analyst/data/live/relay_last_sent.txt"

# 没有新内容就跳过
if [ ! -f "$RELAY_FILE" ]; then
    exit 0
fi

CURRENT=$(cat "$RELAY_FILE")
if [ -z "$CURRENT" ] || [ "$CURRENT" = "无待发送通知" ]; then
    exit 0
fi

# 检查是否和上次一样
PREV=$(cat "$SENT_FILE" 2>/dev/null)
if [ "$CURRENT" = "$PREV" ]; then
    exit 0
fi

NODE="/Applications/AutoClaw.app/Contents/Resources/node/darwin-arm64/node"
OPENCLAW="/Users/sound/Library/Application Support/autoclaw/embedded-gateway-runtime/0aa756dc7703af4d/gateway/openclaw/node_modules/.bin/openclaw"

# 限制消息长度
MSG=$(head -c 800 "$RELAY_FILE")

"$NODE" "$OPENCLAW" agent \
    --agent dao \
    --channel openclaw-weixin \
    --deliver \
    --timeout 30 \
    --message "$MSG" 2>/dev/null

# 记录已发送
cp "$RELAY_FILE" "$SENT_FILE"
