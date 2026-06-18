#!/usr/bin/env python3
"""明日关注 V3.1 — autotrade盘前预演：band池+市场驱动+信号过滤"""
import sys, os, json, urllib.request, ssl, time
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

MAX = 8

# ═══ 板块关键词 ═══
SEC_KW = {
    '电子科技': ['电子','电路','pcb','元件','半导体','芯片','光电'],
    '能源电力': ['电力','能源','煤炭','燃气','发电','水电','火电','核电','光伏'],
    '机械制造': ['机械','制造','设备','重工','精密','机器'],
    '化工材料': ['化工','化学','材料','新材','纤维','橡胶','石化'],
    '金融': ['银行','保险'],
    '消费': ['食品','饮料','酒','零售','服装','消费','纸','包装'],
    '汽车零部件': ['汽车','新能源','锂','电池','零部件','轮胎'],
    '信息技术': ['软件','计算机','数据','通信','5g','网络','ai','智能'],
    '地产基建': ['地产','建筑','建材','水泥','基建','工程','装饰'],
    '医药': ['医药','药','生物','医疗'],
    '有色钢铁': ['钢铁','有色','铜','铝','金','矿','稀土'],
    '交通物流': ['港口','机场','高速','运输','物流','航空'],
}

STOCK_SEC = {
    '泰鸿万立':'汽车零部件','绿田机械':'机械制造','大明电子':'电子科技',
    '福能股份':'能源电力','新集能源':'能源电力','北方国际':'地产基建',
    '生益科技':'电子科技','春秋电子':'电子科技','天洋新材':'化工材料',
    '仙鹤股份':'消费','科达制造':'机械制造','TCL科技':'电子科技',
    '巨轮智能':'机械制造','协鑫能科':'能源电力','天娱数科':'信息技术',
}

def get_sec(name):
    if name in STOCK_SEC: return STOCK_SEC[name]
    for sec, kws in SEC_KW.items():
        if any(kw in name for kw in kws): return sec
    return '综合'

def get_market():
    try:
        raw = urllib.request.urlopen(
            'https://qt.gtimg.cn/q=sh000001,sz399001,sz399006', timeout=5
        ).read().decode('gbk')
        chgs = []
        for ln in raw.strip().splitlines():
            d = ln.split('~')
            if len(d) >= 33: chgs.append(float(d[32]))
        avg = sum(chgs) / len(chgs) if chgs else 0
    except:
        avg = 0
    
    if avg > 1.5:
        return avg, '🟢进攻', '成长+周期', ['电子','制造','新能源','科技'], ['银行','公用']
    elif avg > 0.3:
        return avg, '🟢偏进攻', '均衡偏成长', ['电子','制造','消费'], []
    elif avg > -0.3:
        return avg, '🟡震荡', '均衡', [], []
    elif avg > -1.5:
        return avg, '🟠偏防御', '均衡偏防御', ['能源','电力','银行'], ['电子','科技']
    else:
        return avg, '🔴防御', '纯防御', ['银行','电力','公用'], ['电子','科技','制造']

def fetch_prices(codes):
    r = {}
    for i in range(0, len(codes), 30):
        b = codes[i:i+30]
        s = ','.join(f'sh{c}' if c.startswith('6') else f'sz{c}' for c in b)
        try:
            raw = urllib.request.urlopen(
                f'https://qt.gtimg.cn/q={s}', timeout=8
            ).read().decode('gbk')
            time.sleep(0.3)
            for ln in raw.strip().splitlines():
                d = ln.split('~')
                if len(d) < 45: continue
                r[d[2]] = {
                    'px': float(d[3]), 'chg': float(d[32]),
                    'pe': float(d[39]) if d[39].replace('.','').replace('-','').isdigit() else 0,
                    'vol_ratio': float(d[48]) if d[48] else 0,
                    'amount': float(d[37]) if d[37] else 0,
                }
        except: pass
    return r

def rank_stocks(stocks, market):
    """与autotrade一致的市场排序"""
    avg_chg, label, style, prefer, avoid = market
    ranked = []
    for s in stocks:
        name = s['name']; sec = get_sec(name)
        sc = 0
        
        # 市场偏好
        if prefer and any(p.lower() in sec.lower() for p in prefer):
            sc += 30
        if avoid and any(a.lower() in sec.lower() for a in avoid):
            sc -= 20
        
        # 池子权重
        pool = s.get('pool', 'watch')
        sc += {'core': 10, 'band': 8, 'value': 6, 'board': 4}.get(pool, 2)
        
        # PE
        pe = s.get('pe', 0)
        if 0 < pe < 15: sc += 10
        elif 15 <= pe < 30: sc += 5
        
        # 信号强度
        import re
        sig_m = re.search(r'信号(\d)/6', s.get('note', ''))
        sig = int(sig_m.group(1)) if sig_m else 0
        sc += sig * 3
        
        ranked.append((sc, s))
    
    ranked.sort(key=lambda x: -x[0])
    return [s for sc, s in ranked], [sc for sc, s in ranked]

def main():
    wl = json.load(open('data/watchlist.json'))
    
    # ═══ 只从 band + core 池取 ═══
    candidates = []
    for gn in ['core', 'band']:
        g = wl['groups'].get(gn, {})
        for s in g.get('stocks', []):
            c = s['code']
            if c.startswith(('300', '688', '8')): continue
            if 'ST' in s.get('name', '') or '退' in s.get('name', ''): continue
            candidates.append({**s, 'pool': gn})
    
    # 去重
    seen = {}
    for s in candidates:
        c = s['code']
        if c not in seen or seen[c].get('pool') != 'core':
            seen[c] = s
    candidates = list(seen.values())
    
    # 市场
    market = get_market()
    avg_chg, label, style, prefer, avoid = market
    
    # 获取行情
    codes = [s['code'] for s in candidates]
    prices = fetch_prices(codes)
    
    # 合并数据
    enriched = []
    for s in candidates:
        c = s['code']
        if c not in prices: continue
        p = prices[c]
        if p['px'] < 3 or p['px'] > 50: continue
        if p['pe'] > 100: continue
        enriched.append({**s, **p})
    
    # 市场排序
    ranked, scores = rank_stocks(enriched, market)
    
    # 板块分散 (同板块最多2只)
    final = []; sec_count = {}
    for s in ranked:
        sec = get_sec(s['name'])
        sec_count.setdefault(sec, 0)
        if sec_count[sec] < 2:
            final.append(s)
            sec_count[sec] += 1
        if len(final) >= MAX:
            break
    
    if not final:
        print('⚠️ 无候选'); return
    
    # ═══ 输出 ═══
    print()
    print(f'🎯 明日关注')
    print(f'📅 {datetime.now().strftime("%Y-%m-%d %H:%M")}  {label}市')
    print(f'🤖 DAO分析师 V3.3 | autotrade盘前预演')
    print()
    print(f'  📈 三指均值{avg_chg:+.1f}% | 风格: {style}')
    if prefer: print(f'  🎯 偏好: {", ".join(prefer)}')
    if avoid: print(f'  ⛔ 避开: {", ".join(avoid)}')
    print()
    
    tiers = [(0, 3, '🛡️ S级 优先'), (3, 6, '⚡ A级 次选'), (6, 8, '🎯 B级 备选')]
    for st, ed, label in tiers:
        ts = final[st:ed]
        if not ts: continue
        if st > 0: print('  ─────────────────────')
        print(f'▸ {label}')
        for i, s in enumerate(ts):
            rk = st + i + 1
            sign = '+' if s['chg'] >= 0 else ''
            pe_str = f'PE{int(s["pe"])}' if s['pe'] > 0 else 'PE-'
            sec = get_sec(s['name'])
            print(f'  {rk:02d} {s["name"]}({s["code"]})')
            print(f'     【{sec}】 ¥{s["px"]:.2f}  {sign}{s["chg"]:.1f}%  {pe_str}')
            tags = []
            if s['pool'] == 'core': tags.append('核心池')
            elif s['pool'] == 'band': tags.append('波段池')
            if s['vol_ratio'] > 1.5: tags.append(f'量{s["vol_ratio"]:.1f}x')
            if '龙头' in s.get('note', ''): tags.append('龙头')
            if tags: print(f'     ✦ {" · ".join(tags)}')
    
    print()
    m = get_market()
    if m[1] in ('🟢进攻', '🟢偏进攻'):
        print('⚔️ 退可守，进可攻 → 轮动低吸')
    elif m[1] in ('🟠偏防御', '🔴防御'):
        print('🛡️ 防御模式 → 高股息+低PE → 控制仓位')
    else:
        print('🔄 震荡模式 → 波段操作 → 买跌不追涨')
    print()
    print('─' * 24)
    print('⚠️ 以上与autotrade共用筛选逻辑，盘中由autotrade执行')
    print('⚠️ 不构成投资建议 · 股市有风险 · 投资需谨慎')

if __name__ == '__main__':
    main()
