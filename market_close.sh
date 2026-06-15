#!/bin/bash
# 收盘停止 — 15:00停止实时监控
# 优先用PID文件,否则用pgrep
if [ -f /tmp/realtime_monitor.pid ]; then
    PID=$(cat /tmp/realtime_monitor.pid)
    kill $PID 2>/dev/null && echo "[$(date)] ✅ 监控已停止 PID=$PID"
    rm -f /tmp/realtime_monitor.pid
fi
# 兜底: pgrep杀掉所有monitor
pkill -f realtime_monitor.py 2>/dev/null && echo "[$(date)] ✅ pkill停止监控" || echo "[$(date)] ⚠️ 无监控进程"
# 清理
rm -f /tmp/realtime_monitor.pid
