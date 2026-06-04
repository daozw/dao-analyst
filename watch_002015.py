#!/usr/bin/env python3
"""协鑫能科 002015 盯盘脚本 — 本周专用"""
import json, os, sys, urllib.request, ssl, time
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

# 关键价位
LEVELS = {
    "SELL": [
        (24.77, "卖200股 → 双顶前沿 +12.6%"),
        (25.63, "卖200股 → 双顶压力 +16.5%"),
        (27.36, "卖200股 → 突破目标 +24.4%"),
    ],
    "STOP": [
        (23.40, "减200股 → 破MA5+斐波38.2%"),
        (22.20, "清400股 → 破MA20趋势转空"),
    ],
    "BUY": [
        (23.66, "加200股 → MA5回踩"),
        (22.84, "加300股 → MA10支撑"),
    ],
}

COST = 22.00
SHARES = 600
ALERT_FILE = "/tmp/dao_trade_alerts.json"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "watch_002015_state.json")

def get_price():
    """获取实时价格"""
    try:
        url = f"https://qt.gtimg.cn/q=sz002015"
        raw = urllib.request.urlopen(urllib.request.Request(url), timeout=5).read().decode("gbk")
        parts = raw.split("~")
        if len(parts) < 10: return None
        return {
            "name": parts[1],
            "price": float(parts[3]),
            "chg": float(parts[32]) if len(parts) > 32 else 0,
            "high": float(parts[33]) if len(parts) > 33 else 0,
            "low": float(parts[34]) if len(parts) > 34 else 0,
        }
    except:
        return None

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"last_price": 0, "triggered": []}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def queue_alert(msg):
    """写入通知队列"""
    alerts = []
    if os.path.exists(ALERT_FILE):
        try:
            alerts = json.load(open(ALERT_FILE))
        except: pass
    alerts.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": "ALERT",
        "code": "002015",
        "name": "协鑫能科",
        "message": msg,
        "sent": False
    })
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

def check():
    data = get_price()
    if not data:
        print("❌ 行情获取失败")
        return

    price = data["price"]
    state = load_state()
    triggered = set(state.get("triggered", []))
    alerts = []

    # 检查各价位
    for category, levels in LEVELS.items():
        for target, msg in levels:
            key = f"{category}:{target}"
            if key in triggered:
                continue

            if category == "SELL" and price >= target:
                alerts.append(f"🔔 {msg} | 现价¥{price:.2f}")
                triggered.add(key)
            elif category == "STOP" and price <= target:
                alerts.append(f"⚠️ {msg} | 现价¥{price:.2f}")
                triggered.add(key)
            elif category == "BUY" and price <= target and price > target * 0.97:
                alerts.append(f"📉 {msg} | 现价¥{price:.2f}")
                triggered.add(key)

    # 状态输出
    profit = (price / COST - 1) * 100
    print(f"协鑫能科 ¥{price:.2f} {data['chg']:+.1f}% | 浮盈{profit:+.1f}%")
    print(f"  高¥{data['high']:.2f} 低¥{data['low']:.2f} | 成本¥{COST:.2f}")
    
    # 最近价位
    next_sell = min((t for t, _ in LEVELS["SELL"] if t > price), default=None)
    next_stop = max((t for t, _ in LEVELS["STOP"] if t < price), default=None)
    if next_sell:
        print(f"  距卖点¥{next_sell:.2f} 差{(next_sell/price-1)*100:+.1f}%")
    if next_stop:
        print(f"  距止损¥{next_stop:.2f} 差{(next_stop/price-1)*100:+.1f}%")

    if alerts:
        print(f"\n  ⚡ 触发 {len(alerts)} 条提醒:")
        for a in alerts:
            print(f"  {a}")
            queue_alert(a)

    state["triggered"] = list(triggered)
    state["last_price"] = price
    save_state(state)

    return alerts

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        os.remove(STATE_FILE) if os.path.exists(STATE_FILE) else None
        print("✅ 状态已重置")
    else:
        check()
