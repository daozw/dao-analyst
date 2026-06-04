#!/usr/bin/env python3
"""
中枢分配器 V1.0 — 观察池→特征匹配→分配到核心/波段/打板
"""
import sys, os, json, warnings, random, time
from datetime import datetime
from collections import Counter
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')

from mootdx.quotes import Quotes
from pipeline.fetcher import _raw_fetch
from pipeline.signals import analyze

WATCHLIST = os.path.expanduser('~/dao-analyst/data/watchlist.json')
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "hub.json")


def screen_all():
    """全市场扫描 → 观察池候选"""
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    mb = all_stocks[mask]
    codes = mb['code'].astype(str).tolist()
    names = dict(zip(mb['code'].astype(str), mb['name']))
    
    wl = json.load(open(WATCHLIST))
    existing = set()
    for g in wl['groups']:
        for s in wl['groups'][g].get('stocks',[]):
            existing.add(s['code'])
    
    # 价值扫描(低PE) + 异动扫描(涨幅+放量)
    sample = random.Random(int(datetime.now().strftime('%Y%m%d'))).sample(codes, min(500, len(codes)))
    
    candidates = []
    t0 = time.time()
    
    for code in sample:
        if time.time() - t0 > 90: break
        try:
            df = q.bars(symbol=code, frequency=9, start=0, offset=30)
            if df is None or df.empty: continue
            df = df.sort_index()
            closes = df['close'].values
            vols = df['volume'].values
            
            chg = (closes[-1] / closes[-2] - 1) * 100
            price = float(closes[-1])
            
            if price < 3 or price > 50: continue
            if code in existing: continue
            
            # 快速过滤: 有异动(涨幅≥2%或跌幅≥2%) 或 放量
            avg_vol = sum(vols[-6:-1])/5 if len(vols)>=6 else vols[-2]
            vol_ratio = vols[-1]/avg_vol if avg_vol>0 else 1
            
            if abs(chg) < 2 and vol_ratio < 2: continue
            
            ma30 = sum(closes[-30:])/30
            ma30_prev = sum(closes[-31:-1])/30
            
            # Full data
            d = _raw_fetch(code, use_cache=False)
            if 'error' in d: continue
            a = analyze(d)
            
            candidates.append({
                'code': code, 'name': d['name'], 'price': price,
                'chg': round(chg,2), 'signal': a['g'], 'pe': d.get('pe',0),
                'vol_ratio': round(vol_ratio,1),
                'ma30_up': ma30 > ma30_prev,
                'turnover': d.get('turnover', 0),
                'entry': a['prices']['first_entry'],
                'stop': a['prices']['stop_loss'],
                'target': a['prices']['take_profit_1'],
                'sector': '综合',
            })
        except: pass
    
    return candidates


def dispatch(candidates):
    """中枢分配: 根据特征分到核心/波段/打板"""
    wl = json.load(open(WATCHLIST))
    
    core = wl['groups']['core']['stocks']
    band = wl['groups']['band']['stocks']
    board = wl['groups']['board']['stocks']
    watch = wl['groups']['watch']['stocks']
    
    core_codes = {s['code'] for s in core}
    band_codes = {s['code'] for s in band}
    board_codes = {s['code'] for s in board}
    
    dispatched = {'core': [], 'band': [], 'board': [], 'watch': []}
    
    for c in candidates:
        code = c['code']
        
        # 核心池条件: 涨幅>5% + 量比>2.5 + MA30↑ + 信号≥3
        if c['chg'] >= 5 and c['vol_ratio'] >= 2.5 and c['ma30_up'] and c['signal'] >= 3:
            if code not in core_codes:
                core.append({"code": code, "name": c['name'], 
                    "note": f"信号{c['signal']}/6 · PE={c['pe']:.0f} · ¥{c['price']:.2f}"})
                core_codes.add(code)
            dispatched['core'].append(c['name'])
        
        # 打板池条件: 涨停 + 低价<¥15 + 换手>5%
        elif c['chg'] >= 9.5 and c['price'] < 15 and c['turnover'] > 5:
            if code not in board_codes:
                board.append({"code": code, "name": c['name'],
                    "note": f"涨停 · ¥{c['price']:.2f} · 换手{c['turnover']:.1f}%"})
                board_codes.add(code)
            dispatched['board'].append(c['name'])
        
        # 波段池条件: 信号≥3 + PE<50 + 价格合理
        elif c['signal'] >= 3 and c['pe'] < 100 and 3 <= c['price'] <= 30:
            if code not in band_codes:
                band.append({"code": code, "name": c['name'],
                    "note": f"信号{c['signal']}/6 · PE={c['pe']:.0f} · ¥{c['price']:.2f}"})
                band_codes.add(code)
            dispatched['band'].append(c['name'])
        
        # 其余: 观察池
        else:
            if code not in {s['code'] for s in watch}:
                watch.append({"code": code, "name": c['name'],
                    "note": f"信号{c['signal']}/6 · 待确认"})
            dispatched['watch'].append(c['name'])
    
    wl['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(WATCHLIST, 'w') as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)
    
    return dispatched


def run_hub():
    """中枢分配主流程"""
    print(f'🎯 中枢分配器 {datetime.now().strftime("%H:%M")}')
    print('='*50)
    
    print('📡 Step 1/3: 全市场扫描...')
    candidates = screen_all()
    print(f'  初筛 {len(candidates)} 只候选')
    
    if not candidates:
        print('  今日无候选')
        return
    
    print(f'\n🔀 Step 2/3: 特征分配...')
    dispatched = dispatch(candidates)
    
    total = sum(len(v) for v in dispatched.values())
    print(f'  分配 {total} 只:')
    print(f'    ⚔️ 核心池 +{len(dispatched["core"])}只 (质量≥30+公式达标)')
    if dispatched["core"]: print(f'       {",".join(dispatched["core"][:5])}')
    print(f'    📊 波段池 +{len(dispatched["band"])}只 (质量≥50+信号≥4)')
    if dispatched["band"]: print(f'       {",".join(dispatched["band"][:5])}')
    print(f'    🎯 打板池 +{len(dispatched["board"])}只 (涨停+质量≥40)')
    print(f'    🗑️ 过滤掉 质量<30的标的')
    print(f'    👀 观察池 +{len(dispatched["watch"])}只 (质量≥30待升级)')
    
    # 状态
    print(f'\n📊 Step 3/3: 池子现状')
    wl = json.load(open(WATCHLIST))
    for g in ['core','band','board','watch']:
        s = wl['groups'].get(g,{}).get('stocks',[])
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f'\n{"="*50}')
    print(f'筛选→观察→中枢分配→核心/波段/打板')


if __name__ == "__main__":
    run_hub()
