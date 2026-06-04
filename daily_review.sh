#!/bin/bash
# 每日复盘 20:15
cd /Users/sound/dao-analyst
.venv/bin/python3 2>/dev/null -c "
import sys, json, os
sys.path.insert(0, '.')
from pipeline.fetcher import fetch, fetch_market
from pipeline.signals import analyze
from datetime import datetime

print('📊 每日复盘', datetime.now().strftime('%Y-%m-%d %H:%M'))
print()

# 大盘
md = fetch_market()
idx = md.get('index', {})
print(f'上证 {idx.get(\"price\",\"-\")} {idx.get(\"chg\",0):+.2f}%')

# 持仓表现（从MX查）
from pipeline.autotrade import get_mx_positions, get_dynamic_capital
try:
    pos, total_val, total_pnl = get_mx_positions()
    cap = get_dynamic_capital()
    print(f'MX持仓 {len(pos)}只 ¥{total_val:,.0f} 盈亏¥{total_pnl:+,.0f}')
    print(f'动态总资金 ¥{cap:,.0f}')
    for code, p in pos.items():
        d = fetch(code, use_cache=False)
        sig = ''
        if 'error' not in d:
            a = analyze(d); sig = f' 信号{a[\"g\"]}/6'
        arrow = '🟢' if p['profit_pct'] > 0 else '🔴' if p['profit_pct'] < 0 else '➖'
        print(f'  {arrow} {p[\"name\"]} {p[\"qty\"]}股 ¥{p[\"value\"]:,.0f} {p[\"profit_pct\"]:+.1f}%{sig}')
except Exception as e:
    print(f'MX查询失败: {e}')

# 波段池
wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
band = wl.get('groups',{}).get('band',{}).get('stocks',[])
print(f'\n波段池信号:')
for s in band:
    d = fetch(s['code'], use_cache=False)
    if 'error' in d: continue
    a = analyze(d)
    can = '✅' if a['g'] >= 3 else '⏳'
    print(f'  {can} {d[\"name\"]} ¥{d[\"price\"]:.2f} {d[\"chg\"]:+.1f}% {a[\"g\"]}/6')
" 2>&1

# Queue alert for agent
.venv/bin/python3 2>/dev/null -c "
import json, os
from datetime import datetime
af = '/tmp/dao_trade_alerts.json'
alerts = []
if os.path.exists(af):
    try: alerts = json.load(open(af))
    except: pass
alerts.append({
    'time': datetime.now().strftime('%H:%M:%S'),
    'action': 'REVIEW',
    'code': '',
    'name': '每日复盘',
    'message': '📊 每日复盘已生成',
    'sent': False
})
with open(af, 'w') as f: json.dump(alerts, f, ensure_ascii=False, indent=2)
"
