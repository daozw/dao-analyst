#!/bin/bash
# 开盘启动 — 09:25启动实时WebSocket监控
cd /Users/sound/dao-analyst

# 启动实时监控(后台运行)
nohup .venv/bin/python3 realtime_watch.py > /tmp/realtime_watch.log 2>&1 &
echo $! > /tmp/realtime_watch.pid
echo "✅ 实时监控已启动 PID=$(cat /tmp/realtime_watch.pid)"
