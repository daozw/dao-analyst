#!/bin/bash
# DAO → 微信推送 v4 (2026-06-29 - 指纹去重)
set -e

[ $(date +%u) -ge 6 ] && exit 0

RELAY_FILE="$HOME/dao-analyst/data/live/relay_pending.txt"
FP_FILE="$HOME/dao-analyst/data/live/relay_fingerprint.txt"
FP_SENT="$HOME/dao-analyst/data/live/relay_fp_sent.txt"
LOG_FILE="$HOME/dao-analyst/logs/relay_cron.log"
CTX_FILE="$HOME/.openclaw-autoclaw/openclaw-weixin/accounts/accd3043ff7d-im-bot.context-tokens.json"
ACCT_FILE="$HOME/.openclaw-autoclaw/openclaw-weixin/accounts/accd3043ff7d-im-bot.json"

BASE_URL="https://ilinkai.weixin.qq.com"
TARGET="o9cq80wRoXDnZLK2e_Z4fWXMSNSs@im.wechat"

[ ! -f "$RELAY_FILE" ] && exit 0
CURRENT=$(cat "$RELAY_FILE")
[ -z "$CURRENT" ] && exit 0

# 指纹去重: 比较信号/交易指纹而非全文
if [ -f "$FP_FILE" ] && [ -f "$FP_SENT" ]; then
    FP_NOW=$(cat "$FP_FILE")
    FP_LAST=$(cat "$FP_SENT")
    [ "$FP_NOW" = "$FP_LAST" ] && exit 0
fi

# 读取 contextToken
CTX_TOKEN=$(python3 -c "
import json
try:
    with open('$CTX_FILE') as f:
        d = json.load(f)
    print(d.get('$TARGET', ''))
except: pass
" 2>/dev/null)

BOT_TOKEN=$(python3 -c "
import json
try:
    with open('$ACCT_FILE') as f:
        d = json.load(f)
    print(d.get('token', ''))
except: pass
" 2>/dev/null)

MSG_TEXT=$(head -c 800 "$RELAY_FILE" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")
CLIENT_ID="oclw-relay-$(date +%s)-$$"

BODY=$(cat <<EOF
{
  "msg": {
    "from_user_id": "",
    "to_user_id": "$TARGET",
    "client_id": "$CLIENT_ID",
    "message_type": 2,
    "message_state": 2,
    "item_list": [{"type": 1, "text_item": {"text": $MSG_TEXT}}],
    "context_token": "$CTX_TOKEN"
  },
  "base_info": {
    "channel_version": "2.4.3",
    "bot_agent": "openclaw-weixin"
  }
}
EOF
)

NOW=$(date '+%H:%M:%S')

HTTP_CODE=$(curl -s -o /tmp/relay_response.txt -w "%{http_code}" \
  -X POST "${BASE_URL}/ilink/bot/sendmessage" \
  -H "Content-Type: application/json" \
  -H "AuthorizationType: ilink_bot_token" \
  -H "iLink-App-Id: bot" \
  -H "iLink-App-ClientVersion: 132099" \
  -H "Authorization: Bearer ${BOT_TOKEN}" \
  -d "$BODY" \
  --max-time 15 2>/dev/null)

if [ "$HTTP_CODE" = "200" ]; then
    cp "$FP_FILE" "$FP_SENT" 2>/dev/null
    echo "[$NOW] ✅" >> "$LOG_FILE"
else
    RESP=$(cat /tmp/relay_response.txt 2>/dev/null | head -c 200)
    echo "[$NOW] ❌ HTTP=$HTTP_CODE $RESP" >> "$LOG_FILE"
fi
