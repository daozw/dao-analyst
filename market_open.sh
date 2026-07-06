#!/bin/bash
cd /Users/sound/dao-analyst
nohup .venv/bin/python3 realtime_monitor.py > /tmp/realtime_monitor_stdout.log 2>&1 &
echo $! > /tmp/realtime_monitor.pid
echo "realtime_monitor PID=$!"
nohup .venv/bin/python3 market_sweeper.py daemon > /tmp/market_sweeper_stdout.log 2>&1 &
echo $! > /tmp/market_sweeper.pid
echo "market_sweeper PID=$!"
