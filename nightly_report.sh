#!/bin/bash
# 情报资讯 V3.0 — 全维度+概念+板块+温度计
cd /Users/sound/dao-analyst
exec 2>/dev/null
.venv/bin/python3 << 'PYEOF' 2>/dev/null
import sys, json, urllib.request, ssl, os, warnings, random
from datetime import datetime
from collections import Counter, defaultdict
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')

def pick_concept(all_concepts, sector, chg):
    if not all_concepts: return '-'
    priority = ['AI应用','AI芯片','机器人','半导体','新能源','光伏','储能','新能源车',
                '军工','航天航空','低空经济','CPO','液冷','算力','数字经济','白酒',
                '电力改革','银行','保险','证券','医药','创新药','黄金','有色']
    scored = []
    for c in all_concepts:
        score = 0
        for i, p in enumerate(priority):
            if p in c: score += len(priority) - i
        if sector != '综合' and sector in c: score += 50
        if chg >= 5 and any(h in c for h in ['改革','经济','智能','新能源','AI']): score += 30
        scored.append((c, score))
    scored.sort(key=lambda x: -x[1])
    return scored[0][0] if scored[0][1] > 0 else (all_concepts[0] if all_concepts else '-')

print(f'🌙 情报资讯  {datetime.now().strftime("%Y-%m-%d %A")}')
print()

# ━━ 大盘+温度 ━━
from pipeline.fetcher import fetch_market
md = fetch_market()
idx = md.get('index',{})
print(f'📊 上证 {idx.get("price","-")}  {idx.get("chg",0):+.2f}%')

from market_thermometer_v2 import get_thermometer
try:
    temp = get_thermometer()
    print(f'🌡️ {temp["level"]}  防御{temp["def_avg"]:+.1f}% vs 进攻{temp["off_avg"]:+.1f}%')
except: pass

# ━━ 板块热度 ━━
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

cm = json.load(open('data/concept_map.json')) if os.path.exists('data/concept_map.json') else {}
sector_map = json.load(open('data/sector_map_v2.json')) if os.path.exists('data/sector_map_v2.json') else {}

sample = random.Random(42).sample(codes, min(350, len(codes)))
results = []
concept_heat = Counter()

for code in sample:
    try:
        df = q.bars(symbol=code, frequency=9, start=0, offset=5)
        if df is None or df.empty or len(df) < 2: continue
        df = df.sort_index()
        last = df.iloc[-1]; prev = df.iloc[-2]
        chg = (last['close'] / prev['close'] - 1) * 100
        vol_ratio = last['volume'] / prev['volume'] if prev['volume'] > 0 else 1
        if abs(chg) < 2 and vol_ratio <= 3: continue
        
        price = float(last['close'])
        sec = sector_map.get(code, '综合')
        conc = cm.get(code, [])
        best = pick_concept(conc, sec, chg)
        
        # 原因
        reason = []
        hot_conc = [c for c in conc if any(h in c for h in ['AI','机器人','半导体','新能源','光伏','军工','白酒','银行'])]
        if hot_conc: reason.append(f'{hot_conc[0]}驱动')
        elif sec != '综合': reason.append(f'{sec}联动')
        if vol_ratio >= 5: reason.append('主力介入' if chg>0 else '恐慌抛售')
        elif vol_ratio >= 3: reason.append('放量' if chg>0 else '放量下挫')
        elif vol_ratio >= 2: reason.append('温和放量')
        else: reason.append('缩量')
        if chg >= 9.8: reason.insert(0,'合力封板')
        elif chg >= 7: reason.insert(0,'资金抢筹')
        elif chg >= 3: reason.insert(0,'资金流入')
        elif chg <= -7: reason.insert(0,'资金出逃')
        elif chg <= -3: reason.insert(0,'获利了结')
        
        # 概念热度统计
        for c in conc:
            if chg > 2: concept_heat[c] += 1
            elif chg < -2: concept_heat[c] -= 1
        
        results.append({'code':code,'name':names.get(code,''),'chg':round(chg,2),
            'sector':sec,'concept':best,'reason':'→'.join(reason),
            'vol':round(vol_ratio,1),'price':price})
    except: pass

# 概念热度TOP
hot_concepts = [(c,n) for c,n in concept_heat.most_common(10) if n > 0 and c not in ['综合','-']]
cold_concepts = [(c,n) for c,n in concept_heat.most_common() if n < 0 and c not in ['综合','-']][:5]

if hot_concepts or cold_concepts:
    print(f'\n📈 概念热度')
    if hot_concepts:
        print(f'  🔥 ', '  '.join(f'{c}+{n}' for c,n in hot_concepts[:5]))
    if cold_concepts:
        print(f'  ❄️ ', '  '.join(f'{c}{n}' for c,n in cold_concepts[:5]))

# ━━ 涨幅TOP10 ━━
results.sort(key=lambda x:-x['chg'])
print(f'\n🔥 涨幅 TOP10')
for r in results[:10]:
    f = '🔴' if r['chg']>=9.8 else '🟠' if r['chg']>=5 else '🟡'
    print(f'{f}{r["name"]:<6} {r["code"]} {r["chg"]:>+5.1f}% ¥{r["price"]:.2f} {r["sector"]}|{r["concept"]}')
    print(f'  {r["reason"]}')

# ━━ 跌幅TOP5 ━━
down = sorted([r for r in results if r['chg']<0], key=lambda x:x['chg'])
print(f'\n❄️ 跌幅 TOP5')
for r in down[:5]:
    f = '🟢' if r['chg']<=-5 else '⚪'
    print(f'{f}{r["name"]:<6} {r["code"]} {r["chg"]:>+5.1f}% ¥{r["price"]:.2f} {r["sector"]}|{r["concept"]}')
    print(f'  {r["reason"]}')

# ━━ 成交额TOP5 ━━
print(f'\n💰 成交额 TOP5')
try:
    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=5&sort=amount&asc=0&node=hs_a&symbol="
    req = urllib.request.Request(url, headers={"Referer":"https://finance.sina.com.cn","User-Agent":"Mozilla/5.0"})
    for s in json.loads(urllib.request.urlopen(req, timeout=10).read().decode("gbk")):
        code = s.get('code','')
        if not code.startswith(('60','00')) or code.startswith('688'): continue
        conc = pick_concept(cm.get(code,[]), sector_map.get(code,''), 0)
        print(f'  {s["name"]:<6} {code} ¥{float(s.get("amount",0))/1e8:.0f}亿 {float(s.get("changepercent",0)):+.1f}% {sector_map.get(code,"-")}|{conc}')
except: pass

# ━━ 持仓 ━━
from pipeline.autotrade import get_mx_positions
pos, tv, tp = get_mx_positions()
print(f'\n📦 持仓 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
for code, p in pos.items():
    if p['qty'] > 0:
        a = '🔴' if p['profit_pct']>0 else '🟢'
        conc = pick_concept(cm.get(code,[]), sector_map.get(code,''), 0)
        print(f'  {a}{p["name"]:<6} {code} {p["qty"]}股 {p["profit_pct"]:>+5.1f}% {sector_map.get(code,"-")}|{conc}')

# ━━ 明日关注 ━━
from pipeline.fetcher import fetch
from pipeline.signals import analyze
print(f'\n📌 明日关注')
wl = json.load(open('data/watchlist.json'))
for s in wl.get('groups',{}).get('band',{}).get('stocks',[]):
    d = fetch(s['code'], use_cache=False)
    if 'error' in d: continue
    a = analyze(d)
    pr = a['prices']
    tag = '✅' if a['g']>=3 else '⏳'
    conc = pick_concept(cm.get(s['code'],[]), sector_map.get(s['code'],''), 0)
    sigs = ','.join(s['label'] for s in a.get('signals',[]) if s['lv']=='g')
    print(f'  {tag} {d["name"]:<6} ¥{d["price"]:.2f} {a["g"]}/6 止¥{pr["take_profit_1"]:.2f} {sector_map.get(s["code"],"-")}|{conc}')
    if sigs: print(f'     {sigs}')

print(f'\nbaostock+新浪 | 3226只概念覆盖 | 零积分')
PYEOF
