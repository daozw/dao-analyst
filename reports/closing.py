#!/usr/bin/env python3
"""收盘简报 — 持仓+交易+波段池"""
import sys, os, json, warnings
from datetime import datetime, timezone, timedelta
import urllib.request, ssl
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run():
    MX_KEY = 'mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8'
    
    # 持仓
    req = urllib.request.Request('https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading/positions',
        data=json.dumps({}).encode(), headers={'apikey':MX_KEY,'Content-Type':'application/json'}, method='POST')
    pos = json.loads(urllib.request.urlopen(req, timeout=10).read())
    data = pos.get('data', pos)
    
    out = [f'📋 收盘简报 {datetime.now().strftime("%H:%M")}']
    tv = 0; tp = 0
    for p in data.get('posList',[]):
        if p['count'] > 0:
            tv += p['value']/1000; tp += p['profit']/1000
    out.append(f'📦 持仓 {sum(1 for p in data.get("posList",[]) if p["count"]>0)}只 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
    for p in data.get('posList',[]):
        if p['count'] > 0:
            out.append(f'  {p["secCode"]} {p.get("secName","")} {p["count"]}股 {p.get("profitPct",0):+.1f}%')
    
    # 今日交易
    req2 = urllib.request.Request('https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading/orders',
        data=json.dumps({}).encode(), headers={'apikey':MX_KEY,'Content-Type':'application/json'}, method='POST')
    orders = json.loads(urllib.request.urlopen(req2, timeout=10).read())
    today = [o for o in orders.get('data',{}).get('orders',[]) 
             if datetime.fromtimestamp(o['time'], tz=timezone(timedelta(hours=8))).strftime('%Y-%m-%d') == datetime.now().strftime('%Y-%m-%d')]
    if today:
        out.append(f'\n📊 今日交易 {len(today)}笔')
        for o in today[-10:]:
            ot = {5:'💰买入',6:'💸卖出'}.get(o.get('type'),'?')
            out.append(f'  {ot} {o.get("secName","")} {o["count"]}股')
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
