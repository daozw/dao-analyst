#!/bin/bash
# 收盘简报 15:10
cd /Users/sound/dao-analyst
.venv/bin/python3 2>/dev/null -c "
import sys, json, os
sys.path.insert(0, '.')
from pipeline.fetcher import fetch, fetch_market
from pipeline.signals import analyze
from datetime import datetime

print('📋 收盘简报', datetime.now().strftime('%Y-%m-%d %H:%M'))
print()

# 大盘
md = fetch_market()
idx = md.get('index', {})
print(f'上证 {idx.get(\"price\",\"-\")} {idx.get(\"chg\",0):+.2f}%')

# MX持仓
from pipeline.autotrade import get_mx_positions, get_dynamic_capital
try:
    pos, total_val, total_pnl = get_mx_positions()
    cap = get_dynamic_capital()
    print(f'\n📦 MX持仓 {len(pos)}只 ¥{total_val:,.0f}')
    for code, p in pos.items():
        arrow = '🔴' if p['profit_pct'] > 0 else '🟢' if p['profit_pct'] < 0 else '➖'
        print(f'  {arrow} {p[\"name\"]} {p[\"qty\"]}股 {p[\"profit_pct\"]:+.1f}%')
    print(f'  总盈亏 ¥{total_pnl:+,.0f} | 动态资金 ¥{cap:,.0f}')
except Exception as e:
    print(f'  MX查询失败: {e}')

# 今日交易
logf = os.path.expanduser('~/dao-analyst/data/trade_log.json')
if os.path.exists(logf):
    logs = json.load(open(logf))
    today = datetime.now().strftime('%Y-%m-%d')
    today_logs = [l for l in logs if l['time'].startswith(today)]
    if today_logs:
        print(f'\n📊 今日交易 {len(today_logs)}笔')
        for l in today_logs:
            e = '💰' if l['action']=='BUY' else '💸'
            print(f'  {e} {l[\"name\"]} {l[\"quantity\"]}股 ¥{l[\"amount\"]:,.0f}')

# 波段池
wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
band = wl.get('groups',{}).get('band',{}).get('stocks',[])
print(f'\n🎯 波段池收盘:')
for s in band:
    d = fetch(s['code'], use_cache=False)
    if 'error' in d: continue
    a = analyze(d)
    print(f'  {d[\"name\"]} ¥{d[\"price\"]:.2f} {d[\"chg\"]:+.1f}% {a[\"g\"]}/6')
" 2>&1

# Queue alert
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
    'action': 'CLOSING',
    'code': '',
    'name': '收盘简报',
    'message': '📋 收盘简报已生成',
    'sent': False
})
with open(af, 'w') as f: json.dump(alerts, f, ensure_ascii=False, indent=2)
"
