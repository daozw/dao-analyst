#!/usr/bin/env python3
"""早盘速报 09:15 — 温度+RSI+头条,15分钟决策窗口"""
import sys, os, json, requests, re
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run():
    out = [f'⚡ 早盘速报 {datetime.now().strftime("%m-%d %H:%M")}']
    out.append(f'(距开盘15分钟)')
    
    # 温度
    try:
        from market_thermometer_v2 import get_thermometer, get_rsi, rsi_signal
        temp = get_thermometer()
        out.append(f'\n🌡️ {temp["level"]}')
        rsi = get_rsi()
        if rsi:
            icon, msg = rsi_signal(rsi)
            out.append(f'📶 {icon} {msg}')
    except: pass
    
    # 关键头条
    try:
        r = requests.get('https://www.stcn.com/', headers={'User-Agent':'Mozilla/5.0'}, timeout=5)
        titles = re.findall(r'title="([^"]{8,60})"', r.text)
        keywords = ['央行','降息','降准','证监会','A股','政策','改革','十五五','国务院']
        hits = [t for t in titles[:5] if any(k in t for k in keywords)]
        if hits:
            out.append(f'\n📰')
            for t in hits[:2]: out.append(f'  {t}')
    except: pass
    
    # 结论
    if '防御主导' in temp.get('level',''):
        out.append(f'\n⚠️ 防御主导 → 控制仓位,回避科技')
    elif '进攻占优' in temp.get('level',''):
        out.append(f'\n✅ 进攻占优 → 可以出手')
    else:
        out.append(f'\n🟡 中性 → 精选个股')
    
    return '\n'.join(out)

if __name__ == '__main__':
    print(run())
