#!/usr/bin/env python3
"""情报资讯图表 — 概念热度+板块轮动+温度计"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os, sys, json
from datetime import datetime
from collections import Counter
import numpy as np

# Try to find Chinese font
font_paths = [
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/Library/Fonts/Arial Unicode.ttf',
]
zh_font = None
for fp in font_paths:
    if os.path.exists(fp):
        zh_font = fp
        break

if zh_font:
    plt.rcParams['font.family'] = 'sans-serif'
    fm.fontManager.addfont(zh_font)
    plt.rcParams['font.sans-serif'] = [fm.FontProperties(fname=zh_font).get_name()]
plt.rcParams['axes.unicode_minus'] = False

def generate_chart(out_path='/tmp/nightly_chart.png'):
    """生成情报资讯可视化图表"""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, '/Users/sound/quant-research/daily_stock_analysis/.venv/lib/python3.12/site-packages')
    
    from mootdx.quotes import Quotes
    import random
    
    q = Quotes.factory(market='std')
    all_stocks = q.stocks()
    ik = ['指数','成指','综指','B股','板块','主题','ETF','LOF','基金','回购']
    mask = (all_stocks['code'].astype(str).str.match(r'^(60[0-35-9]|00[0-3])\d{3}$') &
            ~all_stocks['name'].str.contains('|'.join(ik), na=False) &
            ~all_stocks['name'].str.contains('ST|退', na=False))
    codes = all_stocks[mask]['code'].astype(str).tolist()
    
    cm = json.load(open(os.path.expanduser('~/dao-analyst/data/concept_map.json'))) if os.path.exists(os.path.expanduser('~/dao-analyst/data/concept_map.json')) else {}
    
    sample = random.Random(42).sample(codes, min(200, len(codes)))
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
    
    # Filter out noise
    hot = [(c,n) for c,n in concept_up.most_common(8) if n >= 2 and c not in ['综合','-']]
    cold = [(c,n) for c,n in concept_down.most_common(4) if n >= 2 and c not in ['综合','-']]
    
    if not hot and not cold:
        return None
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
    fig.suptitle(f'概念热度  {datetime.now().strftime("%Y-%m-%d")}', fontsize=14, fontweight='bold')
    
    # 热度榜
    if hot:
        names_h = [c for c,_ in hot]
        vals_h = [n for _,n in hot]
        colors_h = ['#ff4444' if v >= 4 else '#ff8800' for v in vals_h]
        ax1.barh(range(len(names_h)), vals_h, color=colors_h, edgecolor='white')
        ax1.set_yticks(range(len(names_h)))
        ax1.set_yticklabels(names_h)
        ax1.set_title('🔥 热门概念')
        ax1.invert_yaxis()
        for i, v in enumerate(vals_h):
            ax1.text(v + 0.1, i, str(v), va='center')
    
    # 冷门榜
    if cold:
        names_c = [c for c,_ in cold]
        vals_c = [n for _,n in cold]
        ax2.barh(range(len(names_c)), vals_c, color='#44aa44', edgecolor='white')
        ax2.set_yticks(range(len(names_c)))
        ax2.set_yticklabels(names_c)
        ax2.set_title('❄️ 冷门概念')
        ax2.invert_yaxis()
        for i, v in enumerate(vals_c):
            ax2.text(v + 0.1, i, str(v), va='center')
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    return out_path

if __name__ == '__main__':
    path = generate_chart()
    if path:
        print(f'✅ {path}')
    else:
        print('无数据')
