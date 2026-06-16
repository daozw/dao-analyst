#!/usr/bin/env python3
"""通知转发 — 从队列读取 → 输出给Agent发送"""
import json, os, sys
from datetime import datetime

ALERT_FILE = "/Users/sound/dao-analyst/data/live/trade_alerts.json"
DISPATCH_LOG = "/tmp/notify_dispatch.log"

def get_pending_important():
    """只取BUY/SELL/BOARD_LIGHTNING/CLOSING类型的待发通知"""
    if not os.path.exists(ALERT_FILE):
        return []
    alerts = json.load(open(ALERT_FILE))
    return [a for a in alerts 
            if not a.get('sent') 
            and a.get('action') in ('BUY','SELL','BOARD_LIGHTNING','CLOSING','🚀SIG','🔥大单','📈急拉','🔄翻转','⚡抢板','📊波段')]

def format_digest(pending):
    """格式化为一条微信消息"""
    if not pending:
        return None
    
    lines = ["📊 交易通知"]
    # 按类型分组
    buys = [a for a in pending if a.get('action') == 'BUY']
    sells = [a for a in pending if a.get('action') == 'SELL']
    boards = [a for a in pending if a.get('action') == 'BOARD_LIGHTNING']
    closing = [a for a in pending if a.get('action') == 'CLOSING']
    
    if buys:
        lines.append("")
        lines.append("💰 买入:")
        for a in buys[:5]:
            lines.append(f"  {a['name']}({a['code']}) {a.get('quantity','?')}股 @¥{a['price']}")
    
    if sells:
        lines.append("")
        lines.append("💸 卖出:")
        for a in sells[:5]:
            lines.append(f"  {a['name']}({a['code']}) {a.get('quantity','?')}股 @¥{a['price']}")
    
    if boards:
        lines.append("")
        lines.append("⚡ 竞价闪电:")
        for a in boards[:3]:
            lines.append(f"  {a['name']}({a['code']}) {a.get('quantity','?')}股")
    
    return "\n".join(lines)

def mark_all_sent():
    """标记所有已格式化通知为已发"""
    if not os.path.exists(ALERT_FILE):
        return
    alerts = json.load(open(ALERT_FILE))
    for a in alerts:
        if not a.get('sent') and a.get('action') in ('BUY','SELL','BOARD_LIGHTNING','CLOSING','🚀SIG','🔥大单','📈急拉','🔄翻转','⚡抢板','📊波段'):
            a['sent'] = True
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

    # 自动清理旧通知
    try:
        from pipeline.trade_notify import cleanup_old_alerts
        cleanup_old_alerts()
    except: pass

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'mark-sent':
        mark_all_sent()
        print("✅ 已标记已发")
    else:
        pending = get_pending_important()
        if pending:
            msg = format_digest(pending)
            if msg:
                print(msg)
                print(f"\n({len(pending)}条待发)")
        else:
            print("无待发通知")
