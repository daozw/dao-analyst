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
    lines.append(f"📊 {datetime.now().strftime('%H:%M')} DAO通知")
    
    if important:
        lines.append("")
        lines.append("━━ 交易/告警 ━━")
        for a in important[-8:]:
            act = a.get('action','?')
            code = a.get('code','?')
            name = a.get('name','?')
            price = a.get('price', 0)
            emoji = {'BUY':'💰','SELL':'📈','BOARD_LIGHTNING':'⚡','STOP_LOSS':'🛑'}.get(act,'📋')
            lines.append(f"{emoji} {act} {name}({code}) @¥{price} {a.get('time','')}")
    
    if sigs:
        # 信号去重摘要
        from collections import Counter
        sig_count = Counter()
        latest = {}
        for s in sigs:
            key = f"{s.get('name','?')}({s.get('code','?')})"
            sig_count[key] += 1
            latest[key] = s
        
        hot = [(k,v) for k,v in sig_count.items() if v >= 10]
        hot.sort(key=lambda x: -x[1])
        
        if hot:
            lines.append("")
            lines.append(f"━━ 信号({len(sigs)}条/{len(sig_count)}只) ━━")
            for name, cnt in hot[:5]:
                s = latest[name]
                desc = s.get('result','')[:40].replace(name[:4], '').strip()
                lines.append(f"  {name} ×{cnt}  ¥{s.get('price')}  {desc}")
            if len(hot) > 5:
                lines.append(f"  ...还有{len(hot)-5}只活跃")
    
    msg = '\n'.join(lines)
    
    # 写入relay文件
    RELAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RELAY_FILE, 'w') as f:
        f.write(msg)
    
    # 标记所有为已发送
    for a in pending:
        a['sent'] = True
        a['sent_time'] = datetime.now().isoformat()
    
    tmp = str(ALERT_FILE) + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ALERT_FILE)
    
    return msg

if __name__ == '__main__':
    msg = relay()
    if msg:
        print(msg)
    else:
        print("无待发送通知")
