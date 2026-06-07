#!/usr/bin/env python3
"""
晚间资讯 V3.2 — 专业级市场情报
市场综述 + 温度计 + 板块轮动 + 资金流向 + 异动 + 持仓 + 风险提示
"""
import sys, os, json, warnings, random
from datetime import datetime
from news_aggregator import get_market_news
from collections import Counter, defaultdict
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
from mootdx.quotes import Quotes

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def generate_summary(data):
    """用Ollama生成市场综述"""
    try:
        import urllib.request, json as j
        prompt = f"用一句话总结今日A股市场(30字内): 上证{data['idx_chg']:+.2f}%, 防御{data['def_avg']:+.1f}% vs 进攻{data['off_avg']:+.1f}%, 热门概念{','.join(data['hot_c'][:3])}, 跌停{data['limit_down']}家。只输出总结,不要分析。"
        
        req = urllib.request.Request('http://localhost:11434/api/generate',
            data=j.dumps({"model":"deepseek-r1:8b","prompt":prompt,"stream":False}).encode(),
            headers={"Content-Type":"application/json"})
        r = j.loads(urllib.request.urlopen(req, timeout=15).read())
        return r.get('response','').strip().replace('"','')
    except:
        return None


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
    
    # ━━ 1. 大盘+温度 ━━
    from pipeline.fetcher import fetch_market
    md = fetch_market()
    idx = md.get('index',{})
    idx_chg = idx.get('chg',0)
    
    try:
        from market_thermometer_v2 import get_thermometer
        temp = get_thermometer()
    except:
        temp = {'level':'⚪未知','def_avg':0,'off_avg':0}
    
    # 市场综述
    if '防御主导' in temp.get('level',''):
        summary = '银行石油白酒集体走强，资金从科技股撤离，市场避险情绪浓厚'
    elif '防御抬头' in temp.get('level',''):
        summary = '防御板块开始吸金，科技股出现分歧，风格切换进行中'
    elif '进攻占优' in temp.get('level',''):
        summary = '科技成长主导，资金活跃，进攻窗口打开'
    else:
        summary = '市场震荡整理，方向不明，等待催化剂'
    
    direction = '下跌' if idx_chg < -0.3 else '上涨' if idx_chg > 0.3 else '震荡'
    
    # LLM综述
    llm_hot = [c for c,_ in concept_up.most_common(3) if c not in ['综合','-']] if 'concept_up' in dir() else []
    ld = sum(1 for r in results if r['chg'] <= -9.8)
    llm_data = {'idx_chg': idx_chg, 'def_avg': temp.get('def_avg',0), 'off_avg': temp.get('off_avg',0), 
                'hot_c': llm_hot, 'limit_down': ld}
    llm_summary = generate_summary(llm_data)
    out.append(f'\n📊 上证 {idx.get("price","-")}  {idx_chg:+.2f}%  市场{direction}')
    llm_line = generate_summary(llm_data)
    if llm_line:
        out.append(f'🤖 {llm_line}')
    out.append(f'📝 {summary}')
    out.append(f'🌡️ {temp["level"]}  防御{temp["def_avg"]:+.1f}% vs 进攻{temp["off_avg"]:+.1f}%')
    
    # ━━ 2. 扫面 ━━
    sample = random.Random(42).sample(codes, min(250, len(codes)))
    results = []
    concept_up = Counter()
    concept_down = Counter()
    sector_flow = defaultdict(float)  # 板块资金流向(涨跌加权)
    
    for code in sample:
        try:
            df = q.bars(symbol=code, frequency=9, start=0, offset=2)
            if df is None or df.empty or len(df) < 2: continue
            df = df.sort_index()
            chg = (float(df.iloc[-1]['close'])/float(df.iloc[-2]['close'])-1)*100
            vr = float(df.iloc[-1]['volume'])/float(df.iloc[-2]['volume']) if float(df.iloc[-2]['volume'])>0 else 1
            if abs(chg) < 2 and vr <= 3: continue
            price = float(df.iloc[-1]['close'])
            sec = sm.get(code,'综合')
            conc = cm.get(code,[])
            if not conc and sec != '综合': conc = [sec]
            
            # 概念热度
            for c in conc:
                if chg > 2: concept_up[c] += 1
                elif chg < -2: concept_down[c] += 1
            
            # 板块资金流向
            sector_flow[sec] += chg * float(df.iloc[-1]['volume'])
            
            results.append({'code':code,'name':names.get(code,''),'chg':round(chg,2),
                'price':price,'sec':sec,'conc':conc[0] if conc else '-','vr':vr})
        except: pass
    
    # ━━ 3. 板块轮动 ━━
    # 资金流入TOP5和流出TOP5板块
    flow_sorted = sorted(sector_flow.items(), key=lambda x: -x[1])
    inflow = [(s, f/1e9) for s, f in flow_sorted[:4] if f > 0]
    outflow = [(s, f/1e9) for s, f in flow_sorted[-4:] if f < 0]
    
    if inflow or outflow:
        out.append(f'\n💰 资金流向')
        if inflow:
            out.append(f'  流入: ' + '  '.join(f'{s}+{f:.1f}亿' for s,f in inflow))
        if outflow:
            out.append(f'  流出: ' + '  '.join(f'{s}{f:.1f}亿' for s,f in outflow))
    
    # ━━ 4. 概念热度 ━━
    hot_c = [(c,n) for c,n in concept_up.most_common(5) if n > 0 and c not in ['综合','-']]
    cold_c = [(c,n) for c,n in concept_down.most_common(3) if n > 0 and c not in ['综合','-']]
    if hot_c or cold_c:
        out.append(f'\n📈 概念热度')
        if hot_c:
            out.append(f'  🔥 ' + '  '.join(f'{c}+{n}' for c,n in hot_c))
        if cold_c:
            out.append(f'  ❄️ ' + '  '.join(f'{c}-{n}' for c,n in cold_c))
    
    # ━━ 5. 涨幅TOP10 ━━
    results.sort(key=lambda x:-x['chg'])
    out.append(f'\n🔥 今日涨幅 TOP10')
    for r in results[:10]:
        f='🔴' if r['chg']>=9.8 else '🟠' if r['chg']>=5 else '🟡'
        out.append(f'  {f}{r["name"]:<6} {r["code"]} {r["chg"]:>+5.1f}% ¥{r["price"]:.2f} {r["sec"]}|{r["conc"]}')
    
    # ━━ 6. 跌幅TOP5 ━━
    down = sorted([r for r in results if r['chg']<0], key=lambda x:x['chg'])
    out.append(f'\n❄️ 今日跌幅 TOP5')
    for r in down[:5]:
        f='🟢' if r['chg']<=-5 else '⚪'
        out.append(f'  {f}{r["name"]:<6} {r["code"]} {r["chg"]:>+5.1f}% ¥{r["price"]:.2f} {r["sec"]}|{r["conc"]}')
    
    # ━━ 7. 持仓 ━━
    try:
        from pipeline.autotrade import get_mx_positions
        pos, tv, tp = get_mx_positions()
        out.append(f'\n📦 策略持仓 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
        for code, p in pos.items():
            if p['qty'] > 0:
                a = '🔴' if p['profit_pct']>0 else '🟢'
                out.append(f'  {a}{p["name"]:<6} {p["qty"]}股 {p["profit_pct"]:>+5.1f}%')
    except: pass
    
    # ━━ 8. 要闻 ━━
    news = get_market_news()
    if news:
        out.append(f'
📰 市场要闻')
        for line in news.split('
'):
            out.append(line)
    
    # ━━ 9. 实盘持仓 ━━
    rp_file = os.path.expanduser('~/dao-analyst/data/real_positions.json')
    if os.path.exists(rp_file):
        rp = json.load(open(rp_file))
        out.append(f'\n💼 实盘持仓')
        from pipeline.fetcher import fetch
        total_rv = 0; total_rp = 0
        for pos in rp.get('positions', []):
            d = fetch(pos['code'], use_cache=False)
            if 'error' not in d:
                pnl = (d['price'] - pos['cost']) * pos['shares']
                pnl_pct = (d['price']/pos['cost']-1)*100
                total_rv += d['price'] * pos['shares']
                total_rp += pnl
                a = '🔴' if pnl > 0 else '🟢'
                out.append(f'  {a}{pos["name"]} {pos["shares"]}股 ¥{d["price"]:.2f} {pnl_pct:+.1f}%')
        out.append(f'  市值¥{total_rv:,.0f} 盈亏¥{total_rp:+,.0f}')
    
    # ━━ 10. 明日风险提示 ━━
    risks = []
    if '防御主导' in temp.get('level',''):
        risks.append('⚠️ 防御主导 → 科技股回避，控制仓位')
    if down and down[0]['chg'] <= -9.8:
        risks.append('⚠️ 有跌停个股 → 注意恐慌蔓延')
    if concept_down.get('半导体',0) >= 2 or concept_down.get('AI应用',0) >= 2:
        risks.append('⚠️ 科技概念持续失血 → 不要抄底')
    
    if risks:
        out.append(f'\n⚠️ 明日风险')
        for r in risks:
            out.append(f'  {r}')
    
    out.append(f'\nbaostock | 3226只概念 | 零积分')
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
