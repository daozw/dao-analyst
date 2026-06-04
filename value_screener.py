#!/usr/bin/env python3
"""价值发现 V1.1 — 快速扫描低估值标的"""
import sys, os, json, warnings, random, time
from datetime import datetime
from collections import Counter
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALERT_FILE = "/tmp/dao_trade_alerts.json"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "value.json")

sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
from mootdx.quotes import Quotes

def scan_value_stocks():
    print(f'💎 价值发现  {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    mb = all_stocks[mask]
    codes = mb['code'].astype(str).tolist()
    names = dict(zip(mb['code'].astype(str), mb['name']))
    
    # Load band pool
    wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
    band_codes = {s['code'] for s in wl.get('groups',{}).get('band',{}).get('stocks',[])}
    
    # Sector map
    sector_map = {}
    smf = os.path.expanduser('~/dao-analyst/data/sector_map_v2.json')
    if os.path.exists(smf): sector_map = json.load(open(smf))
    
    # Sample + fast mootdx scan
    sample = random.Random(int(datetime.now().strftime('%Y%m%d'))).sample(codes, min(300, len(codes)))
    
    results = []
    t0 = time.time()
    
    from pipeline.fetcher import _raw_fetch, _cache
    from pipeline.signals import analyze
    
    for i, code in enumerate(sample):
        if time.time() - t0 > 90:  # 90s timeout
            break
        try:
            # Fast mootdx check first
            df = q.bars(symbol=code, frequency=9, start=0, offset=3)
            if df is None or df.empty or len(df) < 2: continue
            df = df.sort_index()
            last = df.iloc[-1]; prev = df.iloc[-2]
            chg = (last['close'] / prev['close'] - 1) * 100
            price = float(last['close'])
            
            # Quick filter
            if price < 3 or price > 30: continue
            if chg < -2 or chg > 5: continue
            if code in band_codes: continue
            
            # Fetch full data for signal analysis
            d = _raw_fetch(code, use_cache=False)
            if 'error' in d: continue
            
            a = analyze(d)
            sig = a['g']
            if sig < 2: continue
            
            good_sigs = [s['label'] for s in a.get('signals', []) if s['lv'] == 'g']
            sec = sector_map.get(code, '综合')
            pe = d.get('pe', 0)
            
            # Only include if PE is reasonable or signal is strong
            if pe > 50 and sig < 4: continue
            
            results.append({
                'code': code, 'name': d['name'], 'price': price,
                'chg': chg, 'signal': sig, 'pe': pe,
                'sector': sec,
                'good_signals': ','.join(good_sigs),
                'entry': a['prices']['first_entry'],
                'stop': a['prices']['stop_loss'],
                'target': a['prices']['take_profit_1'],
            })
        except:
            pass
    
    results.sort(key=lambda x: (-x['signal'], -len(x['good_signals'].split(','))))
    
    elapsed = time.time() - t0
    print(f'  扫描{min(i+1, len(sample))}只 | {len(results)}只通过 | {elapsed:.0f}s')
    
    if not results:
        print('  今日无合适标的')
        return results
    
    # 板块分布
    sec_dist = Counter(r['sector'] for r in results)
    bars = '  '.join(f'{s}{"█"*c}{c}' for s,c in sec_dist.most_common(5) if s!='综合')
    if bars: print(f'  📈 {bars}')
    
    print(f'\n  {"名称":<8}{"代码":<7}{"信号":>4}{"现价":>8}{"PE":>6}{"板块":<6}{"建仓":>8}{"止盈":>8}{"信号详情"}')
    
    for r in results[:10]:
        arrow = '🔴' if r['chg'] >= 3 else '🟢' if r['chg'] <= -1 else '➖'
        print(f'  {arrow}{r["name"]:<7}{r["code"]:<7}{r["signal"]:>3}/6{r["price"]:>8.2f}{r["pe"]:>6.0f}{r["sector"]:<6}{r["entry"]:>8.2f}{r["target"]:>8.2f}{r["good_signals"]}')
    
    # Save
    state = {"date": datetime.now().strftime("%Y-%m-%d"), "picks": [{"code": r["code"], "name": r["name"], "signal": r["signal"]} for r in results[:10]]}
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    # Alert
    if results[:5]:
        alerts = []
        if os.path.exists(ALERT_FILE):
            try: alerts = json.load(open(ALERT_FILE))
            except: pass
        for r in results[:5]:
            alerts.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "action": "VALUE", "code": r["code"], "name": r["name"],
                "message": f"💎 {r['name']}({r['code']}) {r['signal']}/6 PE={r['pe']:.0f} ¥{r['price']:.2f}",
                "sent": False
            })
        with open(ALERT_FILE, "w") as f:
            json.dump(alerts, f, ensure_ascii=False, indent=2)
    
    print(f'\n  编辑 watchlist.json→band.stocks 加入波段池')
    return results

if __name__ == "__main__":
    scan_value_stocks()
