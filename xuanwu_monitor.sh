#!/bin/bash
cd /Users/sound/dao-analyst

# 市场温度检查
TEMP=$(.venv/bin/python3 -c "from market_thermometer_v2 import get_thermometer; t=get_thermometer(); print(t['level'])" 2>/dev/null)

if echo "$TEMP" | grep -q "防御主导"; then
    echo "🔴 防御主导 → 打板暂停"
    exit 0
fi

# 自动交易
.venv/bin/python3 pipeline/xuanwu_trade.py auto 2>&1
