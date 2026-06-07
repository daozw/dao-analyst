#!/usr/bin/env python3
"""午间简报 — 持仓+异动+下午策略"""
import sys, os, json, warnings, random
from datetime import datetime
from collections import Counter
import urllib.request, ssl
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
from mootdx.quotes import Quotes

def run():
    out = [f'☀️ 午间简报 {datetime.now().strftime("%H:%M")}']
    
    # 持仓
    try:
        from pipeline.autotrade import get_mx_positions
        pos, tv, tp = get_mx_positions()
        out.append(f'📦 持仓 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
        for code, p in pos.items():
            if p['qty'] > 0:
                a = '🔴' if p['profit_pct']>0 else '🟢'
                out.append(f'  {a}{p["name"]} {p["qty"]}股 {p["profit_pct"]:+.1f}%')
    except: pass
    
    # 快速异动
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    codes = all_stocks[mask]['code'].astype(str).tolist()
    names = dict(zip(all_stocks[mask]['code'].astype(str), all_stocks[mask]['name']))
    
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
    
    if hits:
        hits.sort(key=lambda x:-x[2])
        out.append(f'\n🔥 异动:')
        for c,n,chg in hits[:5]:
            out.append(f'  {chg:>+5.1f}% {n} {c}')
    
    # 温度
    try:
        from market_thermometer_v2 import get_thermometer
        t = get_thermometer()
        out.append(f'\n🌡️ {t["level"]}')
    except: pass
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
