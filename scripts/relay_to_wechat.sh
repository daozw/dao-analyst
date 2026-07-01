#!/bin/bash
# DAO → 微信推送 v6 (2026-07-01 - 15分钟最小间隔,内容去重)
set -e

[ $(date +%u) -ge 6 ] && exit 0

RELAY_FILE="$HOME/dao-analyst/data/live/relay_pending.txt"
FP_FILE="$HOME/dao-analyst/data/live/relay_fingerprint.txt"
FP_SENT="$HOME/dao-analyst/data/live/relay_fp_sent.txt"
CONTENT_SENT="$HOME/dao-analyst/data/live/relay_content_sent.txt"
LOG_FILE="$HOME/dao-analyst/logs/relay_cron.log"
CTX_FILE="$HOME/.openclaw-autoclaw/openclaw-weixin/accounts/accd3043ff7d-im-bot.context-tokens.json"
ACCT_FILE="$HOME/.openclaw-autoclaw/openclaw-weixin/accounts/accd3043ff7d-im-bot.json"

BASE_URL="https://ilinkai.weixin.qq.com"
TARGET="o9cq80wRoXDnZLK2e_Z4fWXMSNSs@im.wechat"
MIN_INTERVAL=900  # 最小推送间隔15分钟

[ ! -f "$RELAY_FILE" ] && exit 0
CURRENT=$(cat "$RELAY_FILE")
[ -z "$CURRENT" ] && exit 0

# 提取核心(前5只股票,去emoji)
CORE=$(echo "$CURRENT" | grep -E "^  [0-9]{6}" | head -5 | sed 's/ 🆕//g')
[ -z "$CORE" ] && exit 0

# 判断是否需要推送
SKIP=0

if [ -f "$CONTENT_SENT" ]; then
    CORE_LAST=$(cat "$CONTENT_SENT")
    
    # 计算核心重合度(几只股票和上次一样)
    OVERLAP=$(comm -12 <(echo "$CORE" | sort) <(echo "$CORE_LAST" | sort) | wc -l | tr -d ' ')
    
    if [ "$OVERLAP" -ge 5 ]; then
        # 前5完全一致 → 永远跳过
        SKIP=1
    elif [ "$OVERLAP" -ge 4 ]; then
        # 前5只中4只相同 → 检查间隔,15分钟内跳过
        if [ -f "$FP_SENT" ]; then
            LAST_TS=$(stat -f %m "$FP_SENT" 2>/dev/null || echo 0)
            NOW_TS=$(date +%s)
            if [ $((NOW_TS - LAST_TS)) -lt "$MIN_INTERVAL" ]; then
                SKIP=1
            fi
        fi
    fi
    # 重合度≤3 → 内容明显变化,推送
fi

if [ "$SKIP" = "1" ]; then
    exit 0
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
    echo "$CORE" > "$CONTENT_SENT"
    echo "[$NOW] ✅" >> "$LOG_FILE"
else
    RESP=$(cat /tmp/relay_response.txt 2>/dev/null | head -c 200)
    echo "[$NOW] ❌ HTTP=$HTTP_CODE $RESP" >> "$LOG_FILE"
fi
