#!/bin/bash
# 实时监控看门狗: 交易时段每5分钟检查,挂了就重启
HOUR=$(date +%H)
MINUTE=$(date +%M)

# 仅在交易时段 09:30-15:00
if [ "$HOUR" -lt 9 ] || [ "$HOUR" -gt 15 ]; then exit 0; fi
if [ "$HOUR" -eq 9 ] && [ "$MINUTE" -lt 30 ]; then exit 0; fi
if [ "$HOUR" -eq 15 ] && [ "$MINUTE" -gt 0 ]; then exit 0; fi

if ! pgrep -f realtime_monitor.py > /dev/null; then
    cd /Users/sound/dao-analyst
    nohup .venv/bin/python3 realtime_monitor.py >> /tmp/realtime_monitor.log 2>&1 &
    echo "[$(date '+%H:%M:%S')] 🔄 看门狗重启监控" >> /tmp/realtime_monitor.log
fi
