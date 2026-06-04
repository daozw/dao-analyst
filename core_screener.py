#!/usr/bin/env python3
"""核心作战池筛选 — 主力净买+量比+MA30+涨幅+净资产"""
import sys, os, json, warnings, random, time
from datetime import datetime
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')

from mootdx.quotes import Quotes
from pipeline.fetcher import _raw_fetch
from pipeline.signals import analyze

WATCHLIST = os.path.expanduser('~/dao-analyst/data/watchlist.json')
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "core.json")

def screen_core_pool():
    """盘后筛选核心作战池: 基于当日实际涨幅>5% + 放量 + MA30↑ + 净资产>0
   收盘后运行,为次日提供候选"""
    print(f'⚔️ 核心作战筛选 {datetime.now().strftime("%H:%M")}')
    
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    mb = all_stocks[mask]
    codes = mb['code'].astype(str).tolist()
    names = dict(zip(mb['code'].astype(str), mb['name']))
    
    # Load existing pools
    wl = json.load(open(WATCHLIST))
    existing = set()
    for g in ['core','band','board']:
        for s in wl['groups'].get(g,{}).get('stocks',[]):
            existing.add(s['code'])
    
    sample = random.Random(int(datetime.now().strftime('%Y%m%d'))).sample(codes, min(500, len(codes)))
    results = []
    t0 = time.time()
    
    for code in sample:
        if time.time() - t0 > 90: break
        try:
            df = q.bars(symbol=code, frequency=9, start=0, offset=30)
            if df is None or df.empty or len(df) < 25: continue
            df = df.sort_index()
            closes = df['close'].values
            vols = df['volume'].values
            
            chg = (closes[-1] / closes[-2] - 1) * 100
            if chg < 5: continue  # 涨幅<5%不过
            
            ma30 = sum(closes[-30:]) / 30
            ma30_prev = sum(closes[-31:-1]) / 30
            if ma30 <= ma30_prev: continue  # MA30未向上
            
            avg_vol = sum(vols[-6:-1]) / 5 if len(vols) >= 6 else vols[-2]
            vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 1
            if vol_ratio < 2: continue  # 量比<2
            
            price = float(closes[-1])
            if price < 3 or price > 30: continue
            if code in existing: continue
            
            # Full data for signal
            d = _raw_fetch(code, use_cache=False)
            if 'error' in d: continue
            
            a = analyze(d)
            sig = a['g']
            pe = d.get('pe', 0)
            
            if sig < 2: continue
            
            results.append({
                'code': code, 'name': d['name'], 'price': price, 'chg': round(chg,2),
                'signal': sig, 'pe': pe, 'vol_ratio': round(vol_ratio,1),
                'entry': a['prices']['first_entry'],
                'stop': a['prices']['stop_loss'],
                'target': a['prices']['take_profit_1'],
            })
        except: pass
    
    results.sort(key=lambda x: (-x['signal'], -x['vol_ratio']))
    
    elapsed = time.time() - t0
    print(f'  扫描{min(len(sample),500)}只 | {len(results)}只通过 | {elapsed:.0f}s')
    
    if results:
        print(f'\n  {"名称":<8}{"代码":<7}{"信号":>4}{"涨幅":>6}{"量比":>5}{"现价":>8}{"PE":>6}{"建仓":>8}{"止损":>8}')
        for r in results[:8]:
            print(f'  🔴{r["name"]:<7}{r["code"]:<7}{r["signal"]:>3}/6{r["chg"]:>+5.1f}%{r["vol_ratio"]:>4.1f}x{r["price"]:>8.2f}{r["pe"]:>6.0f}{r["entry"]:>8.2f}{r["stop"]:>8.2f}')
        
        # Update core pool
        core = wl['groups']['core']['stocks']
        existing_codes = {s['code'] for s in core}
        added = 0
        for r in results[:5]:
            if r['code'] not in existing_codes:
                core.append({"code": r['code'], "name": r['name'], "note": f"信号{r['signal']}/6 · PE={r['pe']:.0f} · ¥{r['price']:.2f}"})
                added += 1
        
        if added:
            wl['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            with open(WATCHLIST, 'w') as f:
                json.dump(wl, f, ensure_ascii=False, indent=2)
            print(f'\n  ✅ 核心池新增 {added} 只')
    
    # Save state
    state = {"date": datetime.now().strftime("%Y-%m-%d"), "picks": [r['code'] for r in results[:5]]}
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    return results


if __name__ == "__main__":
    screen_core_pool()
