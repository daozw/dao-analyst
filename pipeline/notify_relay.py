#!/usr/bin/env python3
"""通知中继: 读队列→写摘要→供Agent转发微信"""
import json, os, time
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ALERT_FILE = BASE / "data" / "live" / "trade_alerts.json"
RELAY_FILE = BASE / "data" / "live" / "relay_pending.txt"

def relay():
    if not ALERT_FILE.exists():
        return
    
    try:
        alerts = json.load(open(ALERT_FILE))
    except:
        return
    
    pending = [a for a in alerts if not a.get('sent')]
    if not pending:
        return
    
    # 只取重要通知
    important = [a for a in pending if a.get('action') in 
        ('BUY', 'SELL', 'BOARD', 'BOARD_LIGHTNING', 'CLOSING', 'STOP_LOSS',
         'ERROR', 'ALERT', 'SYSTEM')]
    
    # 信号类只取摘要
    sigs = [a for a in pending if a.get('action') == '🚀SIG']
    
    lines = []
    now_str = datetime.now().strftime('%H:%M')
    lines.append(f"📊 {now_str} DAO通知")
    # 大盘指数
    try:
        import urllib.request
        raw=urllib.request.urlopen('https://qt.gtimg.cn/q=sh000001,sz399001',timeout=3).read().decode('gbk')
        idx_info=[]
        for ln in raw.strip().split(chr(10)):
            d=ln.split('~')
            if len(d)>32:
                idx_info.append(f"{d[1]} {float(d[3]):.0f} {d[32]}%")
        if idx_info:
            lines.append('  '.join(idx_info))
    except: pass
    
    if important:
        buys = [a for a in important if a.get('action') == 'BUY']
        sells = [a for a in important if a.get('action') in ('SELL', 'STOP_LOSS')]
        boards = [a for a in important if a.get('action') in ('BOARD_LIGHTNING', 'BOARD')]
        
        if buys:
            lines.append("")
            lines.append("💰 买入:")
            for a in buys[-5:]:
                lines.append(f"  {a['name']}({a['code']}) {a.get('quantity','?')}股 @¥{a['price']} {a.get('time','')}")
        if sells:
            lines.append("")
            lines.append("📉 卖出:")
            for a in sells[-5:]:
                lines.append(f"  {a['name']}({a['code']}) {a.get('quantity','?')}股 @¥{a['price']} {a.get('time','')}")
        if boards:
            lines.append("")
            lines.append("⚡ 打板:")
            for a in boards[-3:]:
                lines.append(f"  {a['name']}({a['code']}) @¥{a['price']} {a.get('time','')}")
    
    if sigs:
        # 简洁信号: 按涨幅排序,去重去噪
        seen = {}
        top_chg = []
        for s in sigs:
            code = s.get('code','')
            chg = s.get('price', 0)
            try:
                chg_pct = float(str(s.get('result','')).split('+')[1].split('%')[0]) if '+' in str(s.get('result','')) else 0
            except: chg_pct = 0
            if code not in seen or chg_pct > seen[code][0]:
                seen[code] = (chg_pct, s)
        for code, (pct, s) in seen.items():
            top_chg.append((pct, s))
        top_chg.sort(key=lambda x: -x[0])
        
        if top_chg:
            lines.append("")
            lines.append(f"━━ 📡 关注({len(top_chg)}只) ━━")
            for pct, s in top_chg[:10]:
                code = s['code']
                name = s.get('name','?')
                price = s.get('price', 0)
                lines.append(f"  {code} {name} +{pct:.1f}% ¥{price}")
    
    msg = '\n'.join(lines)
    
    # 写入relay文件
    RELAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RELAY_FILE, 'w') as f:
        f.write(msg)
    
    # 不标记已发送 — 由 relay_to_wechat.sh 推送后负责标记
    pass
    
    return msg

if __name__ == '__main__':
    msg = relay()
    if msg:
        print(msg)
    else:
        print("无待发送通知")
