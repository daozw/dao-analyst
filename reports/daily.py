#!/usr/bin/env python3
"""每日复盘 20:15 — 盈亏+交易+信号+展望"""
import sys, os, json, warnings, urllib.request, ssl
from datetime import datetime, timezone, timedelta
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MX_KEY = 'mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8'
MX_API = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

def run():
    out = [f'📊 每日复盘 {datetime.now().strftime("%Y-%m-%d %A")}']
    
    # ══ 今日盈亏 ══
    out.append(f'\n── 盈亏 ──')
    try:
        req = urllib.request.Request(f'{MX_API}/positions', data=json.dumps({}).encode(),
            headers={'apikey':MX_KEY,'Content-Type':'application/json'}, method='POST')
        pos = json.loads(urllib.request.urlopen(req, timeout=10).read())
        data = pos.get('data', pos)
        tv = 0; tp = 0
        for p in data.get('posList',[]):
            if p['count'] > 0:
                tv += p['value']/1000; tp += p['profit']/1000
        out.append(f'MX {sum(1 for p in data.get("posList",[]) if p["count"]>0)}只 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
        
        # 实盘
        rp_file = os.path.expanduser('~/dao-analyst/data/real_positions.json')
        if os.path.exists(rp_file):
            rp = json.load(open(rp_file))
            if rp.get('positions'):
                from pipeline.fetcher import fetch
                rv = 0; rp_pnl = 0
                for p in rp['positions']:
                    d = fetch(p['code'], use_cache=False)
                    if 'error' not in d:
                        rv += d['price'] * p['shares']
                        rp_pnl += (d['price'] - p['cost']) * p['shares']
                out.append(f'实盘 {len(rp["positions"])}只 ¥{rv:,.0f} 盈亏¥{rp_pnl:+,.0f}')
            else:
                out.append(f'实盘 空仓')
    except Exception as e:
        out.append(f'盈亏查询失败')
    
    # ══ 今日交易 ══
    out.append(f'\n── 交易 ──')
    try:
        req = urllib.request.Request(f'{MX_API}/orders', data=json.dumps({}).encode(),
            headers={'apikey':MX_KEY,'Content-Type':'application/json'}, method='POST')
        orders = json.loads(urllib.request.urlopen(req, timeout=10).read())
        today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
        today_orders = [o for o in orders.get('data',{}).get('orders',[]) 
                       if datetime.fromtimestamp(o['time'], tz=timezone(timedelta(hours=8))).strftime('%Y-%m-%d') == today]
        if today_orders:
            buys = [o for o in today_orders if o.get('type')==5]
            sells = [o for o in today_orders if o.get('type')==6]
            out.append(f'买入{len(buys)}笔 卖出{len(sells)}笔')
            for o in today_orders[:8]:
                ot = '💰' if o.get('type')==5 else '💸'
                name = o.get('secName','')
                qty = o['count']
                price = o.get('tradePrice', o['price'])/(10**o.get('priceDec',2))
                out.append(f'  {ot} {name} {qty}股 ¥{price:.2f}')
        else:
            out.append('今日无交易')
    except:
        out.append('交易查询失败')
    
    # ══ 信号 ─═
    out.append(f'\n── 信号 ──')
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze
    wl = json.load(open(os.path.expanduser('~/dao-analyst/data/watchlist.json')))
    for pool in ['core','band']:
        stocks = wl['groups'].get(pool,{}).get('stocks',[])
        if not stocks: continue
        buyable = []; waiting = []
        for s in stocks[:15]:
            d = fetch(s['code'], use_cache=False)
            if 'error' in d: continue
            a = analyze(d)
            if a['g'] >= 3 and -2 < d['chg'] < 5:
                buyable.append(f'  ✅ {d["name"]} {a["g"]}/6 ¥{d["price"]:.2f}')
            elif a['g'] >= 3:
                waiting.append(f'  ⏳ {d["name"]} {a["g"]}/6 {d["chg"]:+.1f}%(涨幅超标)')
        
        name = wl['groups'][pool]['name']
        if buyable or waiting:
            out.append(f'{name}:')
            for b in buyable[:3]: out.append(b)
            for w in waiting[:2]: out.append(w)
    
    # ══ 展望 ─═
    out.append(f'\n── 展望 ──')
    try:
        from market_thermometer_v2 import get_thermometer
        t = get_thermometer()
        if '防御主导' in t.get('level',''):
            out.append(f'⚠️ 防御主导 → 明日控制仓位,回避科技')
        elif '进攻占优' in t.get('level',''):
            out.append(f'✅ 进攻占优 → 明日正常交易')
        else:
            out.append(f'🟡 中性 → 精选标的')
    except:
        out.append(f'温度计不可用')
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
