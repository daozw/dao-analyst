#!/bin/bash
# 午间简报 12:00 — 上午回顾+下午准备
cd /Users/sound/dao-analyst
exec 2>/dev/null
.venv/bin/python3 << 'PYEOF' 2>/dev/null
import sys, json, urllib.request, ssl, os, random
from datetime import datetime
from collections import Counter
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, '.')

print(f'☀️ 午间简报 {datetime.now().strftime("%H:%M")}')
print('='*40)

# 1. 上午大盘
from pipeline.fetcher import fetch_market
md = fetch_market()
idx = md.get('index',{})
print(f'上证 {idx.get("price","-")} {idx.get("chg",0):+.2f}%')

# 2. MX持仓
from pipeline.autotrade import get_mx_positions
pos, tv, tp = get_mx_positions()
print(f'\n📦 持仓 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
for code, p in pos.items():
    if p['qty'] > 0:
        a = '🔴' if p['profit_pct']>0 else '🟢'
        # Check if stop moved
        print(f'  {a}{p["name"]:<6} {p["qty"]}股 {p["profit_pct"]:>+5.1f}%')

# 3. 上午打板回顾
from pipeline.fetcher import fetch
from pipeline.signals import analyze
wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
board = wl['groups']['board']['stocks']
print(f'\n🎯 打板池表现:')
for s in board[:5]:
    d = fetch(s['code'], use_cache=False)
    if 'error' in d: continue
    chg = d['chg']
    tag = '🔴涨停' if chg>=9.8 else '🟠'+f'{chg:+.1f}%' if chg>0 else '🟢'+f'{chg:+.1f}%'
    print(f'  {tag} {d["name"]} ¥{d["price"]:.2f}')

# 4. 上午涨幅扫描（快速50只采样）
print(f'\n🔥 上午异动:')
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
from mootdx.quotes import Quotes
q = Quotes.factory(market='std')
all_stocks = q.stocks()
ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
        ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
        ~all_stocks['name'].str.contains('ST|退', na=False))
mb = all_stocks[mask]
codes = mb['code'].astype(str).tolist()
names = dict(zip(mb['code'].astype(str), mb['name']))

sample = random.Random(42).sample(codes, min(100, len(codes)))
hits = []
for code in sample:
    try:
        df = q.bars(symbol=code, frequency=9, start=0, offset=2)
        if df is None or df.empty or len(df)<2: continue
        df = df.sort_index()
        chg = (float(df.iloc[-1]['close'])/float(df.iloc[-2]['close'])-1)*100
        if abs(chg) >= 3: hits.append((code, names.get(code,''), round(chg,2)))
    except: pass

hits.sort(key=lambda x:-x[2])
for c,n,chg in hits[:5]:
    print(f'  {chg:>+5.1f}% {n} {c}')

# 5. 下午策略建议
from market_sentiment import get_market_sentiment
sentiment, detail = get_market_sentiment()
print(f'\n📌 下午: {sentiment} {detail}')

# 6. 波段池下午关注
band = wl['groups']['band']['stocks']
buyable = []
for s in band:
    d = fetch(s['code'], use_cache=False)
    if 'error' in d: continue
    a = analyze(d)
    if a['g'] >= 3 and -2 < d['chg'] < 5:
        buyable.append(f'{d["name"]}({a["g"]}/6 ¥{d["price"]:.2f})')
if buyable:
    print(f'  ✅ 下午可买: {", ".join(buyable[:3])}')

# 通知
af = '/tmp/dao_trade_alerts.json'
alerts = []
if os.path.exists(af):
    try: alerts = json.load(open(af))
    except: pass
alerts.append({'time': datetime.now().strftime('%H:%M:%S'), 'action': 'MIDDAY',
    'message': f'☀️ 午间简报 {tp:+,.0f}', 'sent': False})
with open(af, 'w') as f: json.dump(alerts, f, ensure_ascii=False, indent=2)
PYEOF
