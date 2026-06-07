#!/usr/bin/env python3
"""周末资讯 — 周日晚上推送,一周回顾+下周展望"""
import sys, os, json, warnings
from datetime import datetime
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 新闻→个股映射
def map_news_to_stocks(sector_keywords):
    """根据板块关键词从股票池匹配个股"""
    wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
    sector_map = json.load(open(os.path.expanduser('~/dao-analyst/data/sector_map_v2.json'))) if os.path.exists(os.path.expanduser('~/dao-analyst/data/sector_map_v2.json')) else {}
    all_stocks = []
    for g in ['core','band']:
        for s in wl['groups'].get(g,{}).get('stocks',[]):
            all_stocks.append(s)
    
    matches = []
    for s in all_stocks:
        d = fetch(s['code'], use_cache=False)
        if 'error' in d: continue
        sec = sector_map.get(s['code'], '')
        if any(k in sec for k in sector_keywords) or any(k in s.get('note','') for k in sector_keywords):
            a = analyze(d)
            matches.append({'name':s['name'],'code':s['code'],'signal':a['g'],'chg':d['chg']})
    return sorted(matches, key=lambda x: -x['signal'])[:3]


def run():
    out = [f'📰 周末资讯  {datetime.now().strftime("%Y-%m-%d %A")}']
    out.append('='*45)
    
    # 大盘周回顾
    from pipeline.fetcher import fetch_market
    md = fetch_market()
    idx = md.get('index',{})
    out.append(f'\n📊 上证 {idx.get("price","-")}  周涨跌{idx.get("chg",0):+.2f}%')
    
    # 温度
    try:
        from market_thermometer_v2 import get_thermometer
        temp = get_thermometer()
        out.append(f'🌡️ {temp["level"]}')
    except: pass
    
    # 波段池# 波段池周信号
    wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
    sector_map = json.load(open(os.path.expanduser('~/dao-analyst/data/sector_map_v2.json'))) if os.path.exists(os.path.expanduser('~/dao-analyst/data/sector_map_v2.json')) else {}
    band = wl['groups']['band']['stocks']
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze
    
    buyable = []
    for s in band[:15]:
        d = fetch(s['code'], use_cache=False)
        if 'error' in d: continue
        a = analyze(d)
        if a['g'] >= 3 and -2 < d['chg'] < 5:
            buyable.append(f'{d["name"]}({a["g"]}/6 ¥{d["price"]:.2f})')
    
    if buyable:
        out.append(f'\n📌 下周关注(波段池筛选) ({len(buyable)}只)')
        for b in buyable[:5]:
            out.append(f'  · {b}')
    
    # 周末要闻
    try:
        from news_aggregator import get_market_news
        news = get_market_news()
        if news:
            out.append(f'\n📰 周末要闻')
            # Filter for policy/market-moving news
            keywords = ['央行','降息','降准','证监会','IPO','印花税','LPR','MLF',
                       '政策','改革','重组','国企','并购','利好','利空','监管',
                       'A股','沪指','板块','涨停','跌停','牛市','熊市']
            for line in news.split('\n'):
                if any(k in line for k in keywords):
                    out.append(line)
    except: pass
    
    # 金十政策快讯
    try:
        import requests
        r = requests.get('https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1',
            headers={'User-Agent':'Mozilla/5.0','x-app-id':'bVBF4FyRTn5NJF5n','x-version':'1.0.0'}, timeout=8)
        flashes = r.json().get('data',[])
        policy = []
        keywords2 = ['央行','降息','降准','LPR','MLF','证监会','IPO','注册制',
                    '国务院','政治局','财政部','发改委','政治局','国常会']
        for f in flashes:
            content = f.get('data',{}).get('content','')
            if any(k in content for k in keywords2):
                policy.append(content[:80])
        if policy:
            out.append(f'\n📡 政策快讯')
            for p in policy[:3]:
                out.append(f'  · {p}')
    except: pass
    
    # 周末要闻
    try:
        from news_aggregator import get_market_news
        news = get_market_news()
        if news:
            bullish = []
            bearish = []
            BULL_KEY = ['利好','增持','涨停','底部','反弹','突破','放量','回购','分红',
                       '降息','降准','宽松','刺激','补贴','减税','规划','新政','改革']
            BEAR_KEY = ['利空','减持','跌停','顶部','回落','跌破','缩量','加息',
                       '收紧','监管','处罚','调查','退市','违约','爆雷','下调']
            
            SOURCE_MAP = {'中信建投':'中信建投','国泰海通':'国泰海通','金十数据':'金十',
                         '证券时报':'证券时报','中国证券报':'中证报','新华社':'新华社',
                         '央行':'央行','证监会':'证监会','国务院':'国务院'}
            
            # 板块映射
            SECTOR_MAP = {
                '食品饮料':'食品饮料/白酒','科技':'半导体/AI','金属':'有色/黄金','地产':'地产/基建',
                '银行':'银行/金融','汽车':'新能源车','医药':'医药/创新药','电力':'电力/公用事业',
                '算力':'AI算力/数据中心','基建':'基建/建材','城市更新':'基建/建材/地产',
            }
            
            for line in news.split('\n'):
                if not line.startswith('  ·'): continue
                text = line[4:]
                is_bull = any(k in text for k in BULL_KEY)
                is_bear = any(k in text for k in BEAR_KEY)
                
                # Identify affected sectors
                sectors = []
                for kw, sec in SECTOR_MAP.items():
                    if kw in text: sectors.append(sec)
                sector_str = f' [{",".join(sectors)}]' if sectors else ''
                
                if is_bull and not is_bear:
                    bullish.append(f'  📈 {text}{sector_str}')
                elif is_bear and not is_bull:
                    bearish.append(f'  📉 {text}{sector_str}')
            
            if bullish:
                out.append(f'\n📈 利好')
                for b in bullish[:4]:
                    out.append(b)
            if bearish:
                out.append(f'\n📉 利空')
                for b in bearish[:3]:
                    out.append(b)
    except: pass
    

    # 下周展望
    out.append(f'\n📅 下周展望')
    if '防御主导' in temp.get('level',''):
        out.append('  ⚠️ 防御主导→控制仓位,等风格切换')
        out.append('  👀 关注温度变化,银行/石油走弱则科技回暖')
    else:
        out.append('  ✅ 正常交易,按信号执行')
    
    out.append(f'\n{"="*45}')
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
