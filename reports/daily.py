#!/usr/bin/env python3
"""每日复盘 — 深度回顾+信号更新"""
import sys, os, json, warnings
from datetime import datetime
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.fetcher import fetch
from pipeline.signals import analyze

def run():
    out = [f'📊 每日复盘 {datetime.now().strftime("%Y-%m-%d")}']
    
    wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
    for pool in ['core','band','board','value','watch']:
        stocks = wl['groups'].get(pool,{}).get('stocks',[])
        if not stocks: continue
        name = wl['groups'][pool]['name']
        out.append(f'\n{name} ({len(stocks)}只):')
        for s in stocks[:8]:
            d = fetch(s['code'], use_cache=False)
            if 'error' in d: continue
            a = analyze(d)
            tag = '✅' if a['g']>=3 else '⏳'
            out.append(f'  {tag} {d["name"]} ¥{d["price"]:.2f} {d["chg"]:+.1f}% {a["g"]}/6')
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
