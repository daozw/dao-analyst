#!/usr/bin/env python3
"""晚间资讯 V4.0 — 专业级目录格式"""
import sys, os, json, warnings, random, re
from datetime import datetime
from collections import Counter
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
from mootdx.quotes import Quotes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run():
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    codes = all_stocks[mask]['code'].astype(str).tolist()
    names = dict(zip(all_stocks[mask]['code'].astype(str), all_stocks[mask]['name']))
    
    cm = json.load(open(f'{BASE}/data/concept_map.json')) if os.path.exists(f'{BASE}/data/concept_map.json') else {}
    sm = json.load(open(f'{BASE}/data/sector_map_v2.json')) if os.path.exists(f'{BASE}/data/sector_map_v2.json') else {}
    
    out = [f'🌙 晚间资讯  {datetime.now().strftime("%Y-%m-%d %A")}']
    
    # ━━ 大盘 ━━
    from pipeline.fetcher import fetch_market
    md = fetch_market()
    idx = md.get('index',{})
    idx_chg = idx.get('chg',0)
    
    try:
        from market_thermometer_v2 import get_thermometer
        temp = get_thermometer()
    except:
        temp = {'level':'⚪未知','def_avg':0,'off_avg':0}
    
    # Scan
    sample = random.Random(42).sample(codes, min(200, len(codes)))
    results = []; concept_up = Counter(); concept_down = Counter()
    
    for code in sample:
        try:
            df = q.bars(symbol=code, frequency=9, start=0, offset=2)
            if df is None or df.empty or len(df) < 2: continue
            df = df.sort_index()
            chg = (float(df.iloc[-1]['close'])/float(df.iloc[-2]['close'])-1)*100
            vr = float(df.iloc[-1]['volume'])/float(df.iloc[-2]['volume']) if float(df.iloc[-2]['volume'])>0 else 1
            if abs(chg) < 2 and vr <= 3: continue
            price = float(df.iloc[-1]['close'])
            sec = sm.get(code,'综合'); conc = cm.get(code,[])
            
            for c in conc:
                if chg > 2: concept_up[c] += 1
                elif chg < -2: concept_down[c] += 1
            
            results.append({'code':code,'name':names.get(code,''),'chg':round(chg,2),
                'price':price,'sec':sec,'conc':conc[0] if conc else '-','vr':vr})
        except: pass
    
    # ━━ 大盘 ━━
    up_n = sum(1 for r in results if r['chg']>0)
    down_n = sum(1 for r in results if r['chg']<0)
    lu = sum(1 for r in results if r['chg']>=9.8)
    ld = sum(1 for r in results if r['chg']<=-9.8)
    direction = '下跌' if idx_chg<-0.3 else '上涨' if idx_chg>0.3 else '震荡'
    
    out.append(f'\n━━ 📊 大盘 ━━')
    out.append(f'上证 {idx.get("price","-")}  {idx_chg:+.2f}%  {direction}')
    out.append(f'涨跌比 {up_n/max(down_n,1):.1f}  涨{up_n} 跌{down_n}  涨停{lu} 跌停{ld}')
    
    # ━━ 温度 ━━
    out.append(f'\n━━ 🌡️ 温度 ━━')
    out.append(f'{temp["level"]}')
    out.append(f'  防御 +{temp["def_avg"]:.1f}%  vs  进攻 {temp["off_avg"]:+.1f}%')
    
    # ━━ 概念 ━━
    hot_c = [(c,n) for c,n in concept_up.most_common(5) if n>0 and c not in ['综合','-']]
    cold_c = [(c,n) for c,n in concept_down.most_common(4) if n>0 and c not in ['综合','-']]
    if hot_c or cold_c:
        out.append(f'\n━━ 📈 概念 ━━')
        if hot_c:
            out.append(f'🔥 活跃')
            for c,n in hot_c:
                out.append(f'  {c:<10} {n}只涨')
        if cold_c:
            out.append(f'❄️ 降温')
            for c,n in cold_c:
                out.append(f'  {c:<10} {n}只跌')
    
    # ━━ 涨幅 ━━
    results.sort(key=lambda x:-x['chg'])
    out.append(f'\n━━ 🔥 涨幅 ━━')
    for r in results[:6]:
        f='🔴' if r['chg']>=9.8 else '🟠' if r['chg']>=5 else '🟡'
        out.append(f'{f} {r["name"]:<6}  {r["code"]}  {r["chg"]:>+5.1f}%  ¥{r["price"]:.2f}  {r["sec"]}|{r["conc"]}')
    
    # ━━ 跌幅 ━━
    down = sorted([r for r in results if r['chg']<0], key=lambda x:x['chg'])
    out.append(f'\n━━ ❄️ 跌幅 ━━')
    for r in down[:4]:
        f='🟢' if r['chg']<=-5 else '⚪'
        out.append(f'{f} {r["name"]:<6}  {r["code"]}  {r["chg"]:>+5.1f}%  ¥{r["price"]:.2f}  {r["sec"]}|{r["conc"]}')
    
    # ━━ 要闻 ━━
    from news_aggregator import get_market_news
    try:
        news = get_market_news()
        if news:
            BULL = ['利好','增持','底部','反弹','突破','回购','降息','降准','规划','新政','改革']
            BEAR = ['利空','减持','顶部','回落','跌破','加息','收紧','监管','处罚']
            SRC = {'中信建投':'中信建投','国泰海通':'国泰海通','央行':'央行','证监会':'证监会'}
            
            bullish = []; bearish = []; policy = []
            for line in news.split('\n'):
                if not line.startswith('  ·'): continue
                text = line[4:]
                clean = re.sub(r'<[^>]+>', '', text).strip()
                source = ''
                for kw, src in SRC.items():
                    if kw in clean: source = f'[{src}] '; break
                
                is_bull = any(k in clean for k in BULL)
                is_bear = any(k in clean for k in BEAR)
                is_pol = any(k in clean for k in ['十五五','十四五','国务院','政治局','发改委','规划'])
                
                if is_pol: policy.append(f'{source}{clean}')
                elif is_bull: bullish.append(f'{source}{clean}')
                elif is_bear: bearish.append(f'{source}{clean}')
            
            if policy:
                out.append(f'\n━━ 📡 政策 ━━')
                for p in policy[:3]: out.append(f'  · {p[:100]}')
            if bullish:
                out.append(f'\n━━ 📈 利好 ━━')
                for b in bullish[:3]: out.append(f'  · {b[:100]}')
            if bearish:
                out.append(f'\n━━ 📉 利空 ━━')
                for b in bearish[:2]: out.append(f'  · {b[:100]}')
    except: pass
    
    # ━━ 持仓 ━━
    try:
        from pipeline.autotrade import get_mx_positions
        pos, tv, tp = get_mx_positions()
        out.append(f'\n━━ 📦 持仓 ━━')
        out.append(f'MX  {sum(1 for p in pos.values() if p["qty"]>0)}只  ¥{tv:,.0f}  盈亏 ¥{tp:+,.0f}')
        for code, p in pos.items():
            if p['qty'] > 0:
                a = '🔴' if p['profit_pct']>0 else '🟢'
                out.append(f'  {a} {p["name"]:<6}  {p["qty"]}股  {p["profit_pct"]:>+5.1f}%')
    except: pass
    
    # ━━ 明日 ━━
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze
    wl = json.load(open(f'{BASE}/data/watchlist.json'))
    band = wl['groups']['band']['stocks']
    
    buyable = []
    for s in band[:15]:
        d = fetch(s['code'], use_cache=False)
        if 'error' in d: continue
        a = analyze(d)
        if a['g'] >= 3 and -2 < d['chg'] < 5:
            buyable.append(f'  {d["name"]:<6}  {a["g"]}/6  ¥{d["price"]:.2f}  止¥{a["prices"]["take_profit_1"]:.2f}')
    
    if buyable:
        out.append(f'\n━━ 📌 明日(波段池) ━━')
        for b in buyable[:4]: out.append(b)
    
    # ━━ 风险 ━━
    risks = []
    if '防御主导' in temp.get('level',''): risks.append('防御主导 → 回避科技')
    if up_n < down_n * 0.5: risks.append(f'涨跌比{up_n/max(down_n,1):.1f} → 市场极弱')
    if ld > 0: risks.append('有跌停 → 警惕蔓延')
    
    if risks:
        out.append(f'\n━━ ⚠️ 风险 ━━')
        for r in risks: out.append(f'  {r}')
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
