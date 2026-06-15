#!/bin/bash
# 开盘启动 — 09:30启动实时监控
cd /Users/sound/dao-analyst

# 杀掉旧进程
if [ -f /tmp/realtime_monitor.pid ]; then
    kill $(cat /tmp/realtime_monitor.pid) 2>/dev/null
    sleep 1
fi

# 启动实时监控(后台运行)
nohup .venv/bin/python3 realtime_monitor.py > /tmp/realtime_monitor_stdout.log 2>&1 &
echo $! > /tmp/realtime_monitor.pid
echo "✅ 实时监控已启动 PID=$(cat /tmp/realtime_monitor.pid)"
