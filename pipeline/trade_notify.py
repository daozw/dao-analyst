#!/usr/bin/env python3
"""交易通知 — 记录交易并生成待推送消息"""
import json, os, sys
from datetime import datetime

LOG_FILE = os.path.expanduser("~/dao-analyst/data/trade_log.json")
ALERT_FILE = "/tmp/dao_trade_alerts.json"

def log_trade(action, code, name, price, quantity, amount, result):
    """记录交易到本地日志"""
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            logs = json.load(open(LOG_FILE))
        except:
            logs = []
    
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "code": code,
        "name": name,
        "price": round(price, 2),
        "quantity": quantity,
        "amount": round(amount, 2),
        "result": result
    }
    logs.append(entry)
    logs = logs[-500:]
    with open(LOG_FILE, "w") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    return entry

def queue_alert(action, code, name, price, quantity, amount, result):
    """写入待推送队列（agent读取后发送微信）"""
    # 去重: 同股票同action同价格5分钟内不重复
    from datetime import datetime as _dt
    now = _dt.now()
    alert = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": action,  # BUY / SELL
        "code": code,
        "name": name,
        "price": round(price, 2),
        "quantity": quantity,
        "amount": round(amount, 2),
        "result": str(result),
        "sent": False
    }
    
    alerts = []
    if os.path.exists(ALERT_FILE):
        try:
            alerts = json.load(open(ALERT_FILE))
        except:
            alerts = []
    
    # 去重检查
    dup = False
    for a in alerts:
        if (a.get('code') == code and a.get('action') == action and 
            a.get('price') == price and not a.get('sent', False)):
            dup = True; break
    if not dup:
        alerts.append(alert)
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

def notify_trade(action, code, name, price, quantity, result="成功"):
    """记录+排队，返回通知文本"""
    amount = price * quantity
    entry = log_trade(action, code, name, price, quantity, amount, result)
    queue_alert(action, code, name, price, quantity, amount, result)
    
    emoji = "💰" if action == "BUY" else "💸"
    return f"{emoji} {action} {name}({code}) {quantity}股 @¥{price:.2f} = ¥{amount:,.0f}"

def get_pending_alerts():
    """获取未发送的通知"""
    if not os.path.exists(ALERT_FILE):
        return []
    try:
        alerts = json.load(open(ALERT_FILE))
        return [a for a in alerts if not a.get("sent", False)]
    except:
        return []

def mark_sent(count):
    """标记前N条为已发送"""
    if not os.path.exists(ALERT_FILE):
        return
    alerts = json.load(open(ALERT_FILE))
    sent = 0
    for a in alerts:
        if not a.get("sent", False) and sent < count:
            a["sent"] = True
            sent += 1
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

def today_summary():
    if not os.path.exists(LOG_FILE):
        return "今日无交易"
    logs = json.load(open(LOG_FILE))
    today = datetime.now().strftime("%Y-%m-%d")
    today_logs = [l for l in logs if l["time"].startswith(today)]
    if not today_logs:
        return "今日无交易"
    
    lines = ["📊 今日交易"]
    for l in today_logs:
        e = "💰买入" if l["action"] == "BUY" else "💸卖出"
        lines.append(f"  {e} {l['name']} {l['quantity']}股 @¥{l['price']:.2f} = ¥{l['amount']:,.0f}")
    return "\n".join(lines)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    if cmd == "pending":
        alerts = get_pending_alerts()
        if alerts:
            for a in alerts:
                e = "💰" if a["action"] == "BUY" else "💸"
                print(f"{e} {a['action']} {a['name']}({a['code']}) {a['quantity']}股 @¥{a['price']:.2f} = ¥{a['amount']:,.0f} [{a['time']}]")
            print(f"\n共 {len(alerts)} 条待发送")
        else:
            print("无待发送通知")
    elif cmd == "mark-sent":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 999
        mark_sent(count)
        print(f"已标记 {count} 条为已发送")
    elif cmd == "summary":
        print(today_summary())
