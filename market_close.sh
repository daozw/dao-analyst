#!/bin/bash
# 收盘停止 — 15:00停止实时监控
if [ -f /tmp/realtime_watch.pid ]; then
    kill $(cat /tmp/realtime_watch.pid) 2>/dev/null
    rm -f /tmp/realtime_watch.pid
    echo "✅ 实时监控已停止"
else
    echo "无运行中的监控"
fi
