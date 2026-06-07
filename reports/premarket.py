#!/usr/bin/env python3
"""盘前简报 09:28 — 消息+技术+策略 三大模块"""
import sys, os, json, requests, re
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run():
    out = [f'🌅 盘前简报 {datetime.now().strftime("%m-%d %H:%M")}']
    
    # ══ 消息面 ══
    out.append(f'\n── 消息面 ──')
    try:
        # 证券时报
        r = requests.get('https://www.stcn.com/', headers={'User-Agent':'Mozilla/5.0'}, timeout=5)
        titles = re.findall(r'title="([^"]{8,60})"', r.text)
        keywords = ['央行','降息','降准','证监会','IPO','政策','改革','重组','A股','十五五','十四五','国务院']
        for t in titles[:3]:
            if any(k in t for k in keywords):
                out.append(f'  📰 {t}')
        # 金十
        r = requests.get('https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1',
            headers={'User-Agent':'Mozilla/5.0','x-app-id':'bVBF4FyRTn5NJF5n'}, timeout=5)
        flashes = r.json().get('data',[])
        pk = ['央行','降息','降准','LPR','MLF','证监会','国务院','政治局','财政部']
        for f in flashes[:10]:
            txt = re.sub(r'<[^>]+>','',f.get('data',{}).get('content',''))
            if any(k in txt for k in pk) and len(txt) > 10 and len(out) < 8:
                out.append(f'  📡 {txt[:80]}')
    except: pass
    
    if len(out) == 2:
        out.append('  (暂无重要消息)')
    
    # ══ 技术面 ══
    out.append(f'\n── 技术面 ──')
    try:
        from market_thermometer_v2 import get_thermometer, get_rsi, rsi_signal
        t = get_thermometer()
        out.append(f'🌡️ {t["level"]}')
        out.append(f'   防御 +{t["def_avg"]:.1f}% vs 进攻 {t["off_avg"]:+.1f}%')
        rsi = get_rsi()
        icon, msg = rsi_signal(rsi)
        out.append(f'📶 {icon} {msg}')
    except:
        out.append('🌡️ 温度计不可用')
    
    # ══ 策略面 ══
    out.append(f'\n── 策略面 ──')
    try:
        from pipeline.autotrade import get_mx_positions
        pos, tv, tp = get_mx_positions()
        out.append(f'📦 MX {len(pos)}只 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
    except: pass
    
    wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
    band = wl['groups']['band']['stocks']
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze
    
    buyable = []
    for s in band[:20]:
        d = fetch(s['code'], use_cache=False)
        if 'error' in d: continue
        a = analyze(d)
        if a['g'] >= 3 and -2 < d['chg'] < 5:
            shares = int(600 / max(d['price'] - a['prices']['stop_loss'], 0.01) / 100) * 100
            if shares >= 100:
                buyable.append(f'  {d["name"]} {a["g"]}/6 ¥{d["price"]:.2f} {shares}股')
    
    if buyable:
        out.append(f'📌 可买 ({len(buyable)}只)')
        for b in buyable[:5]: out.append(b)
    else:
        out.append('📌 今日无买入信号')
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
