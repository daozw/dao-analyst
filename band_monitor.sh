#!/bin/bash
cd /Users/sound/dao-analyst

HOUR=$(date +%H)
MIN=$(date +%M)

# 市场温度
TEMP=$(.venv/bin/python3 -c "from market_thermometer_v2 import get_thermometer; t=get_thermometer(); print(t['level'])" 2>/dev/null)

if echo "$TEMP" | grep -q "防御主导"; then
    echo "🔴 防御主导 暂停买入"
elif echo "$TEMP" | grep -q "防御抬头"; then
    echo "🟠 防御抬头 半仓"
fi

# 正常交易
.venv/bin/python3 pipeline/autotrade.py --real 2>&1
