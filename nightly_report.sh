#!/bin/bash
# 情报资讯 V2.6 — 精选最相关概念
cd /Users/sound/dao-analyst
exec 2>/dev/null
.venv/bin/python3 << 'PYEOF' 2>/dev/null
import sys, json, urllib.request, ssl, os, warnings, random
from datetime import datetime
from collections import Counter
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')

def pick_concept(code, all_concepts, sector, chg):
    """从概念列表中选出最相关的异动概念"""
    if not all_concepts: return '-'
    
    # 优先级排序：热门>行业匹配>通用
    priority = ['人工智能','半导体','新能源','光伏','储能','机器人','军工',
                '低空经济','CPO','液冷','算力','数据要素','鸿蒙','固态电池',
                'HBM','飞行汽车','电力改革','数字经济','新材料','消费电子',
                '汽车零部件','创新药','碳中和','信创','工业母机','无人驾驶']
    
    scored = []
    for c in all_concepts:
        score = 0
        # 热门概念加分
        for i, p in enumerate(priority):
            if p in c: score += len(priority) - i
        # 与板块匹配加分
        if sector != '综合' and sector in c: score += 50
        # 涨停时优先题材概念
        if chg >= 5 and any(h in c for h in ['改革','经济','智能','新能源']): score += 30
        scored.append((c, score))
    
    scored.sort(key=lambda x: -x[1])
    return scored[0][0] if scored[0][1] > 0 else (all_concepts[0] if all_concepts else '-')

print(f'🌙 情报资讯  {datetime.now().strftime("%Y-%m-%d %A")}')
print()

from pipeline.fetcher import fetch_market
md = fetch_market()
idx = md.get('index',{})
print(f'📊 上证 {idx.get("price","-")}  {idx.get("chg",0):+.2f}%')

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

sector_map = {}; concept_map = {}
if os.path.exists('/Users/sound/dao-analyst/data/sector_map_v2.json'): sector_map = json.load(open('/Users/sound/dao-analyst/data/sector_map_v2.json'))
if os.path.exists('/Users/sound/dao-analyst/data/sector_precise.json'):
    sp = json.load(open('/Users/sound/dao-analyst/data/sector_precise.json'))
    for code, info in sp.items():
        if info.get('industry','综合') != '综合': sector_map[code] = info['industry']
        c = info.get('concepts',[]);
        if c and c != ['无']: concept_map[code] = c[:5]

HOT = ['人工智能','半导体','新能源','光伏','储能','机器人','军工','低空','CPO','液冷','算力','数据','鸿蒙','固态电池','HBM','飞行汽车','电力改革','数字经济']

sample = random.Random(42).sample(codes, min(350, len(codes)))
results = []
for code in sample:
    try:
        df = q.bars(symbol=code, frequency=9, start=0, offset=5)
        if df is None or df.empty or len(df) < 2: continue
        df = df.sort_index()
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (last['close'] / prev['close'] - 1) * 100
        vol_ratio = last['volume'] / prev['volume'] if prev['volume'] > 0 else 1
        if len(df) >= 4: streak = (last['close'] / df.iloc[-4]['close'] - 1) * 100
        else: streak = 0
        
        if abs(chg) >= 2 or vol_ratio > 3:
            sec = sector_map.get(code, '综合')
            all_conc = concept_map.get(code, [])
            best_conc = pick_concept(code, all_conc, sec, chg)
            hot_conc = [c for c in all_conc if any(h in c for h in HOT)]
            
            reason = []
            if hot_conc: reason.append(f'{hot_conc[0]}驱动')
            elif sec != '综合': reason.append(f'{sec}联动')
            if vol_ratio >= 5: reason.append('主力大举介入' if chg>0 else '恐慌抛售')
            elif vol_ratio >= 3: reason.append('放量拉升' if chg>0 else '放量下挫')
            elif vol_ratio >= 2: reason.append('温和放量' if chg>0 else '缩量调整')
            else: reason.append('缩量上涨' if chg>0 else '缩量下跌')
            if chg >= 9.8: reason.insert(0,'合力封板')
            elif chg >= 7: reason.insert(0,'资金抢筹')
            elif chg >= 3: reason.insert(0,'资金流入')
            elif streak >= 15: reason.append(f'3日+{streak:.0f}%')
            elif chg <= -7: reason.insert(0,'资金出逃')
            elif chg <= -3: reason.insert(0,'获利了结')
            if streak >= 15 and chg >= 9.5: reason.insert(0,f'连板+{streak:.0f}%')
            
            results.append({
                'code':code,'name':names.get(code,''),'chg':round(chg,2),
                'sector':sec,'concept':best_conc,
                'reason':'→'.join(reason),'vol':round(vol_ratio,1),
                'price':round(float(last['close']),2)
            })
    except: pass

sector_up = Counter(r['sector'] for r in results if r['chg']>0 and r['sector']!='综合')
print(f'\n{"─"*55}')
print(f'📈 板块热度')
for s, c in sector_up.most_common(6):
    print(f'  {s:<8} {"█"*c} {c}')

results.sort(key=lambda x:-x['chg'])
print(f'\n{"─"*55}')
print(f'🔥 涨幅 TOP10')
for r in results[:10]:
    f = '🔴' if r['chg']>=9.8 else '🟠' if r['chg']>=5 else '🟡'
    print(f'{f}{r["name"]:<6} {r["code"]} {r["chg"]:>+5.1f}% ¥{r["price"]:.2f} {r["sector"]} | {r["concept"]}')
    print(f'  {r["reason"]}')

down = sorted([r for r in results if r['chg']<0], key=lambda x:x['chg'])
print(f'\n{"─"*55}')
print(f'❄️ 跌幅 TOP5')
for r in down[:5]:
    f = '🟢' if r['chg']<=-5 else '⚪'
    print(f'{f}{r["name"]:<6} {r["code"]} {r["chg"]:>+5.1f}% ¥{r["price"]:.2f} {r["sector"]} | {r["concept"]}')
    print(f'  {r["reason"]}')

print(f'\n{"─"*55}')
print(f'💰 成交额 TOP5')
try:
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=5&sort=amount&asc=0&node=hs_a&symbol="
    req = urllib.request.Request(url, headers={"Referer":"https://finance.sina.com.cn","User-Agent":"Mozilla/5.0"})
    for s in json.loads(urllib.request.urlopen(req, timeout=10).read().decode("gbk")):
        code = s.get('code','')
        if not code.startswith(('60','00')) or code.startswith('688'): continue
        sec = sector_map.get(code,'-')
        conc = pick_concept(code, concept_map.get(code,[]), sec, 0)
        print(f'  {s["name"]:<6} {code} ¥{float(s.get("amount",0))/1e8:.0f}亿 {float(s.get("changepercent",0)):+.1f}% {sec} | {conc}')
except: pass

from pipeline.autotrade import get_mx_positions
pos, tv, tp = get_mx_positions()
print(f'\n{"─"*55}')
print(f'📦 持仓 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
for code, p in pos.items():
    if p['qty'] > 0:
        a = '🔴' if p['profit_pct']>0 else '🟢'
        sec = sector_map.get(code,'-')
        conc = pick_concept(code, concept_map.get(code,[]), sec, 0)
        print(f'  {a}{p["name"]:<6} {code} {p["qty"]}股 {p["profit_pct"]:>+5.1f}% ¥{p["value"]:,.0f} {sec} | {conc}')

from pipeline.fetcher import fetch
from pipeline.signals import analyze
print(f'\n{"─"*55}')
print(f'📌 明日')
wl = json.load(open('/Users/sound/dao-analyst/data/watchlist.json'))
for s in wl.get('groups',{}).get('band',{}).get('stocks',[]):
    d = fetch(s['code'], use_cache=False)
    if 'error' in d: continue
    a = analyze(d)
    pr = a['prices']
    tag = '✅' if a['g']>=3 else '⏳'
    sec = sector_map.get(s['code'],'-')
    conc = pick_concept(s['code'], concept_map.get(s['code'],[]), sec, 0)
    sigs = ','.join(s['label'] for s in a.get('signals',[]) if s['lv']=='g')
    print(f'  {tag} {d["name"]:<6} {s["code"]} {a["g"]}/6 ¥{d["price"]:.2f} 止¥{pr["take_profit_1"]:.2f} {sec} | {conc} | {sigs}')

print(f'\n{"─"*55)}')
print(f'通达信+新浪 | 零积分 | 概念智能匹配')
PYEOF
