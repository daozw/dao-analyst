#!/bin/bash
cd /Users/sound/dao-analyst

HOUR=$(date +%H)
MIN=$(date +%M)

# 市场情绪检查
SENTIMENT=$(.venv/bin/python3 -c "from market_sentiment import get_market_sentiment; print(get_market_sentiment()[0])" 2>/dev/null)

if [ "$SENTIMENT" = "🔴谨慎" ]; then
    echo "🔴 市场谨慎 暂停交易"
    exit 0
fi

# 14:50 尾盘特殊处理: 只检查止损,不新开仓
if [ "$HOUR" = "14" ] && [ "$MIN" = "50" ]; then
    .venv/bin/python3 -c "
import sys; sys.path.insert(0,'.')
from pipeline.autotrade import auto_trade
# 尾盘仅止损模式
result, _ = auto_trade(dry_run='--real' not in '')
print(result)
" 2>&1
else
    .venv/bin/python3 pipeline/autotrade.py --real 2>&1
fi
