#!/usr/bin/env python3
"""ASCII图表 — 零依赖,毫秒级渲染"""
import os, sys, json, random
from collections import Counter
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
from mootdx.quotes import Quotes

def bar_chart(items, width=30, title=''):
    """水平柱状图"""
    if not items: return ''
    lines = [f'\n{title}']
    max_val = max(n for _,n in items)
    max_name = max(len(c) for c,_ in items)
    for name, val in items:
        bar_len = int(val/max_val*width) if max_val > 0 else 0
        bar = '█' * bar_len + '░' * (width - bar_len)
        lines.append(f'  {name:<{max_name+1}} {bar} {val}')
    return '\n'.join(lines)

def heat_grid(items, cols=5):
    """热度网格"""
    if not items: return ''
    lines = ['\n📈 概念热度']
    row = []
    for i, (name, val) in enumerate(items):
        if val >= 5: icon = '🔥'
        elif val >= 3: icon = '🟠'
        elif val >= 2: icon = '🟡'
        else: icon = '⚪'
        row.append(f'{icon} {name}+{val}')
        if (i+1) % cols == 0 or i == len(items)-1:
            lines.append('  ' + '  '.join(row))
            row = []
    return '\n'.join(lines)

def thermometer(def_avg, off_avg):
    """温度计"""
    ratio = abs(def_avg / max(abs(off_avg), 0.01))
    level = '🔴防御主导' if ratio >= 1.5 else '🟠防御抬头' if ratio >= 1.0 else '🟢进攻占优'
    total = max(abs(def_avg), abs(off_avg)) * 3
    bar_len = 20
    
    def_pos = int(abs(def_avg)/max(total, 0.01)*bar_len) if def_avg > 0 else 0
    off_pos = int(abs(off_avg)/max(total, 0.01)*bar_len) if off_avg > 0 else 0
    
    lines = [f'\n🌡️ {level}  防御{def_avg:+.1f}% vs 进攻{off_avg:+.1f}%']
    
    # Visual bar
    bar = ['─'] * (bar_len * 2)
    mid = bar_len
    for i in range(mid - def_pos, mid):
        if i >= 0: bar[i] = '🟦'
    for i in range(mid, mid + off_pos):
        if i < len(bar): bar[i] = '🟥'
    bar[mid] = '┃'
    
    lines.append(f"  防御{' ' * (bar_len-2)}┃{' ' * (bar_len-2)}进攻")
    lines.append(f'  {"".join(bar)}')
    lines.append(f'  {"←" if def_pos > off_pos else "→"} {"防御主导" if ratio >= 1.5 else "进攻占优" if ratio < 0.8 else "均衡"}')
    return '\n'.join(lines)

def generate():
    """生成ASCII可视化报告"""
    out = []
    
    # 温度
    try:
        from market_thermometer_v2 import get_thermometer
        t = get_thermometer()
        out.append(thermometer(t['def_avg'], t['off_avg']))
    except: pass
    
    # 概念
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    codes = all_stocks[mask]['code'].astype(str).tolist()
    
    cm = json.load(open(os.path.expanduser('~/dao-analyst/data/concept_map.json'))) if os.path.exists(os.path.expanduser('~/dao-analyst/data/concept_map.json')) else {}
    
    sample = random.Random(42).sample(codes, min(150, len(codes)))
    concept_up = Counter()
    concept_down = Counter()
    
    for code in sample:
        try:
            df = q.bars(symbol=code, frequency=9, start=0, offset=2)
            if df is None or df.empty or len(df) < 2: continue
            df = df.sort_index()
            chg = (float(df.iloc[-1]['close'])/float(df.iloc[-2]['close'])-1)*100
            if abs(chg) < 2: continue
            for c in cm.get(code, []):
                if chg > 2: concept_up[c] += 1
                elif chg < -2: concept_down[c] += 1
        except: pass
    
    # 过滤有效概念
    VALID = ['机器人','人工智能','半导体','新能源','光伏','储能','军工','白酒','银行','数字经济',
             '新能源车','低空经济','固态电池','芯片','AI应用','消费电子','创新药','电力','煤炭',
             '石油石化','有色','钢铁','证券','保险','地产','基建','化工','新材料','智能制造']
    
    hot = [(c,n) for c,n in concept_up.most_common(15) if n >= 2 and c in VALID]
    cold = [(c,n) for c,n in concept_down.most_common(8) if n >= 2 and c in VALID]
    
    if hot:
        out.append(heat_grid(hot[:10]))
        out.append(bar_chart(hot[:8], 20, '━━━ 概念热度 TOP8 ━━━'))
    
    if cold:
        out.append(bar_chart(cold[:5], 20, '━━━ 概念降温 TOP5 ━━━'))
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(generate())
