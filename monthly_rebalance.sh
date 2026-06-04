#!/bin/bash
# 月度再平衡 — 每月1号检查核心/卫星比例
cd /Users/sound/dao-analyst
.venv/bin/python3 -c "
import json, sys
sys.path.insert(0,'.')
from pipeline.autotrade import get_mx_positions
pos, tv, tp = get_mx_positions()

core_target = 20000 * 0.7  # 70%核心
sat_target = 20000 * 0.3   # 30%卫星

print(f'📊 月度再平衡')
print(f'核心目标: ¥{core_target:,.0f} (70%)')
print(f'卫星目标: ¥{sat_target:,.0f} (30%)')
print(f'当前持仓: ¥{tv:,.0f}')
print(f'偏移: ¥{tv-core_target:+,.0f}')

import json, os
af='/tmp/dao_trade_alerts.json'
alerts=[]
if os.path.exists(af):
    try: alerts=json.load(open(af))
    except: pass
alerts.append({'time':'','action':'REBALANCE','message':f'📊 月度再平衡 当前¥{tv:,.0f}', 'sent':False})
with open(af,'w') as f: json.dump(alerts,f,ensure_ascii=False,indent=2)
" 2>/dev/null
