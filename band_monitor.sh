#!/bin/bash
cd /Users/sound/dao-analyst

HOUR=$(date +%H)
MIN=$(date +%M)

# 市场温度（获取失败→不阻止交易,只打日志）
TEMP=$(.venv/bin/python3 -c "
from market_thermometer_v2 import get_thermometer
t=get_thermometer()
print(t.get('level',''))
" 2>/dev/null)

if [ -z "$TEMP" ]; then
    echo "[$HOUR:$MIN] ⚠️ 温度获取失败→默认执行autotrade"
elif echo "$TEMP" | grep -q "防御主导"; then
    echo "[$HOUR:$MIN] 🔴 防御主导→跳过autotrade"
    exit 0
elif echo "$TEMP" | grep -q "防御抬头"; then
    echo "[$HOUR:$MIN] 🟠 防御抬头→半仓模式"
fi

# 正常交易
.venv/bin/python3 pipeline/autotrade.py --plan --real 2>&1
echo "[$HOUR:$MIN] ⏳ 等待60秒通知窗口..."
sleep 60
.venv/bin/python3 pipeline/autotrade.py --execute 2>&1
