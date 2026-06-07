#!/bin/bash
cd /Users/sound/dao-analyst

HOUR=$(date +%H)
MIN=$(date +%M)

# 市场温度检查
TEMP=$(.venv/bin/python3 -c "from market_thermometer_v2 import get_thermometer; t=get_thermometer(); print(t['level'])" 2>/dev/null)

if echo "$TEMP" | grep -q "防御主导"; then
    echo "🔴 防御主导 暂停波段买入"
    # 只检查止损，不新开仓
    .venv/bin/python3 -c "
import sys; sys.path.insert(0,'.')
from pipeline.autotrade import auto_trade
# 仅止损模式
result, _ = auto_trade(dry_run='--real' not in '')
print(result)
" 2>&1
    
    # 通知
    .venv/bin/python3 -c "
import json, os
from datetime import datetime
af='/tmp/dao_trade_alerts.json'
alerts=[]
if os.path.exists(af):
    try: alerts=json.load(open(af))
    except: pass
alerts.append({'time':datetime.now().strftime('%H:%M:%S'),'action':'THERMO',
    'message':'🔴 防御主导 暂停买入','sent':False})
with open(af,'w') as f: json.dump(alerts,f,ensure_ascii=False,indent=2)
" 2>/dev/null

elif echo "$TEMP" | grep -q "防御抬头"; then
    echo "🟠 防御抬头 半仓运行"
    .venv/bin/python3 pipeline/autotrade.py --real 2>&1

elif [ "$HOUR" = "14" ] && [ "$MIN" = "50" ]; then
    # 14:50 尾盘正常交易(安全检查已覆盖追高/跌停)
    .venv/bin/python3 pipeline/autotrade.py --real 2>&1
else
    # 正常交易
    .venv/bin/python3 pipeline/autotrade.py --real 2>&1
fi
