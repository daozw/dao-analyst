"""共享通知 — 写入微信推送队列"""
import json, os
from datetime import datetime

ALERT_FILE = "/tmp/dao_trade_alerts.json"

def queue_alert(strategy, action, code, name, price, qty, value, reason=""):
    alerts = []
    if os.path.exists(ALERT_FILE):
        try: alerts = json.load(open(ALERT_FILE))
        except: pass
    alerts.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "strategy": strategy,
        "action": action,
        "code": code, "name": name,
        "price": price, "qty": qty, "value": value,
        "reason": reason,
        "sent": False
    })
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)
