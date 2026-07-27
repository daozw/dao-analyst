#!/bin/bash
# 📨 DAO通知推送 - 替代gateway cron
# 对比 relay_pending vs relay_last_sent，有变化则推送

PENDING="/Users/sound/dao-analyst/data/live/relay_pending.txt"
LAST_SENT="/Users/sound/dao-analyst/data/live/relay_last_sent.txt"
TARGET="o9cq80wRoXDnZLK2e_Z4fWXMSNSs@im.wechat"
LOG="/Users/sound/dao-analyst/logs/cron_push.log"

[ ! -f "$PENDING" ] && exit 0
[ -f "$LAST_SENT" ] && diff -q "$PENDING" "$LAST_SENT" >/dev/null 2>&1 && exit 0

# 有差异 → 推送
CONTENT=$(cat "$PENDING" | head -20)
echo "$(date '+%Y-%m-%d %H:%M:%S') PUSH $(wc -c < "$PENDING") bytes" >> "$LOG"

# 用openclaw CLI推送到微信
/usr/local/bin/openclaw message send \
  --channel openclaw-weixin \
  --target "$TARGET" \
  --message "$CONTENT" \
  >> "$LOG" 2>&1

# 同步last_sent
cp "$PENDING" "$LAST_SENT"
