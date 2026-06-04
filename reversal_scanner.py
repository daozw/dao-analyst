#!/usr/bin/env python3
"""超跌反弹扫描 V1.0 — 反转因子"""
import sys, os, json, warnings, random, time
from datetime import datetime
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
from mootdx.quotes import Quotes

def scan_oversold():
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    mb = all_stocks[mask]
    codes = mb['code'].astype(str).tolist()
    names = dict(zip(mb['code'].astype(str), mb['name']))
    
    sample = random.Random(int(datetime.now().strftime('%Y%m%d'))).sample(codes, min(300, len(codes)))
    results = []
    
    for code in sample:
        try:
            df = q.bars(symbol=code, frequency=9, start=0, offset=20)
            if df is None or df.empty or len(df) < 15: continue
            df = df.sort_index()
            closes = [float(c) for c in df['close'].values]
            vols = [float(v) for v in df['volume'].values]
            
            chg = (closes[-1]/closes[-2]-1)*100
            chg_3d = (closes[-1]/closes[-4]-1)*100 if len(closes)>=4 else 0
            chg_5d = (closes[-1]/closes[-6]-1)*100 if len(closes)>=6 else 0
            price = closes[-1]
            
            # 超跌条件: 3日跌>8%或5日跌>12%,且今日企稳(跌幅<2%)
            is_oversold = (chg_3d <= -8 or chg_5d <= -12) and chg > -2 and price >= 3
            if not is_oversold: continue
            
            vol_ratio = vols[-1]/(sum(vols[-6:-1])/5) if len(vols)>=6 else 1
            
            results.append({
                'code':code,'name':names.get(code,''),'price':round(price,2),
                'chg':round(chg,2),'chg_3d':round(chg_3d,2),'chg_5d':round(chg_5d,2),
                'vol_ratio':round(vol_ratio,1)
            })
        except: pass
    
    results.sort(key=lambda x: x['chg_5d'])
    
    if results:
        print(f'📉 超跌反弹候选 {len(results)}只')
        for r in results[:5]:
            print(f'  {r["name"]}({r["code"]}) 5日{r["chg_5d"]:+.1f}% 今日{r["chg"]:+.1f}% ¥{r["price"]:.2f}')
    
    return results

if __name__ == '__main__':
    scan_oversold()
