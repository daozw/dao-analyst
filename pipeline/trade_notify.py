#!/usr/bin/env python3
"""交易通知 — 记录交易并生成待推送消息 (持久化版)"""
import json, os, sys, fcntl, struct, time
from datetime import datetime

BASE = os.path.expanduser("~/dao-analyst")
ALERT_FILE = os.path.join(BASE, "data", "live", "trade_alerts.json")
LOG_FILE = os.path.join(BASE, "data", "trade_log.json")

def _atomic_read():
    """线程安全读"""
    if not os.path.exists(ALERT_FILE):
        return []
    for _ in range(3):
        try:
            with open(ALERT_FILE, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                data = json.load(f)
                fcntl.flock(f, fcntl.LOCK_UN)
            return data
        except Exception as e:

            log(f"{type(e).__name__}: {e}")  # auto-logged
            time.sleep(0.05)
    return []

def _atomic_write(alerts):
    """原子写: tmp + os.replace"""
    tmp = ALERT_FILE + '.tmp'
    for _ in range(3):
        try:
            with open(tmp, 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(alerts, f, ensure_ascii=False, indent=2)
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, ALERT_FILE)
            return
        except Exception as e:

            log(f"{type(e).__name__}: {e}")  # auto-logged
            time.sleep(0.05)

def queue_alert(action, code, name, price, quantity, amount, result):
    """写入待推送队列"""
    alert = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "code": code,
        "name": name,
        "price": round(price, 2),
        "quantity": quantity,
        "amount": round(amount, 2),
        "result": str(result),
        "sent": False
    }
    
    alerts = _atomic_read()
    
    # 去重: 同股票同action同价格5分钟内不重复
    dup = False
    for a in alerts:
        if (a.get('code') == code and a.get('action') == action 
            and abs(a.get('price', 0) - price) < 0.01):
            try:
                t_a = datetime.strptime(a.get('time', '00:00'), '%H:%M:%S')
                t_new = datetime.strptime(alert['time'], '%H:%M:%S')
                if abs((t_new - t_a).total_seconds()) < 300:
                    dup = True
                    break
            except Exception as e:

                log(f"{type(e).__name__}: {e}")  # auto-logged
                pass
    
    if not dup:
        alerts.append(alert)
        _atomic_write(alerts)
    
    # 同时写交易日志
    log_entry = {**alert, "timestamp": datetime.now().isoformat()}
    _append_log(log_entry)
    
    return not dup

def _append_log(entry):
    """追加交易日志"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            logs = json.load(open(LOG_FILE))
        except Exception as e:

            log(f"{type(e).__name__}: {e}")  # auto-logged
            logs = []
    logs.append(entry)
    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def cleanup_old_alerts(max_age_hours=48, max_count=500):
    """清理过期通知"""
    alerts = _atomic_read()
    now = datetime.now()
    cleaned = []
    for a in alerts:
        try:
            t = datetime.strptime(a.get("time", "00:00"), "%H:%M:%S").replace(year=now.year, month=now.month, day=now.day)
            if (now - t).total_seconds() < max_age_hours * 3600:
                cleaned.append(a)
        except Exception as e:

            log(f"{type(e).__name__}: {e}")  # auto-logged
            cleaned.append(a)
    
    if len(cleaned) > max_count:
        cleaned = cleaned[-max_count:]
    
    _atomic_write(cleaned)
    return len(alerts) - len(cleaned)

def get_pending():
    """获取待发送通知"""
    alerts = _atomic_read()
    return [a for a in alerts if not a.get('sent')]

def mark_sent(indices):
    """标记为已发送"""
    alerts = _atomic_read()
    for i in indices:
        if 0 <= i < len(alerts):
            alerts[i]['sent'] = True
    _atomic_write(alerts)

def get_pending_important():
    """获取重要待发送通知"""
    return [a for a in get_pending() 
            if a.get('action') in ('BUY', 'SELL', 'BOARD_LIGHTNING', 'BOARD', 'CLOSING')]

if __name__ == '__main__':
    import sys
    if 'pending' in sys.argv:
        p = get_pending_important()
        print(f'待发送: {len(p)}条')
        for a in p:
            print(f"  {a['action']} {a['name']}({a['code']}) @¥{a['price']} {a['time']}")
    elif 'mark-sent' in sys.argv and len(sys.argv) > 2:
        idx = int(sys.argv[2])
        mark_sent([idx])
        print(f'已标记 #{idx}')
    elif 'cleanup' in sys.argv:
        n = cleanup_old_alerts()
        print(f'清理 {n} 条过期通知')
    else:
        p = get_pending()
        print(f'队列: {len(p)}待发 / {len(_atomic_read())}总计')

def notify_trade(action, code, name, price, quantity, result):
    """从 autotrade 调用的简化接口"""
    amount = price * quantity
    return queue_alert(action, code, name, price, quantity, amount, result)
