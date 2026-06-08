#!/usr/bin/env python3
"""打板·竞价闪电 V1.0 — 09:22 抢板（抓>7%竞价封板票）"""
import sys, os, json, urllib.request, ssl, subprocess
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALERT_FILE = "/tmp/dao_trade_alerts.json"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "board_lightning.json")
HT_APIKEY = os.environ.get("HT_APIKEY", "ht_2dPFpTyi93kWDXZc5dlI2a7SFyfWCy3Y5cfcVLu2P")
MX_APIKEY = "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8"
MIN_GAP = 7.0; MAX_PRICE = 30

def alert(action, msg):
    alerts = []; ts = datetime.now().strftime('%H:%M:%S')
    if os.path.exists(ALERT_FILE):
        try: alerts = json.load(open(ALERT_FILE))
        except: pass
    alerts.append({'time': ts, 'action': action, 'message': msg, 'sent': False})
    with open(ALERT_FILE, 'w') as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

def get_premarket_lightning():
    try:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node=hs_a&symbol="
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        stocks = json.loads(raw)
        results = []
        for s in stocks:
            code = s.get("code", "")
            if not code.startswith(("60", "00")): continue
            if code.startswith("688"): continue
            if "ST" in s.get("name", "") or "退" in s.get("name", ""): continue
            op = float(s.get("open", 0))
            prev = float(s.get("settlement", 0))
            if prev <= 0: continue
            gap = (op / prev - 1) * 100
            price = float(s.get("trade", 0))
            if gap >= MIN_GAP and price <= MAX_PRICE:
                results.append({
                    "code": code, "name": s.get("name", ""),
                    "price": price, "gap": round(gap, 2),
                    "vol": float(s.get("volume", 0)),
                    "limit_up": round(prev * 1.099 + 0.01, 2)
                })
        return sorted(results, key=lambda x: x['gap'], reverse=True)
    except Exception as e:
        print(f"  ⚠️ 竞价数据获取失败: {e}")
        return []

def submit_mx_order(code, name, price, qty):
    try:
        data = json.dumps({
            "secCode": code, "secName": name,
            "price": price, "count": qty,
            "orderType": "LIMIT", "tradeType": "BUY"
        }).encode()
        req = urllib.request.Request(
            "https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading/order",
            data=data, headers={"apikey": MX_APIKEY, "Content-Type": "application/json"},
            method="POST"
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
        return resp.get("code") == 0 or resp.get("ok") == True
    except Exception as e:
        print(f"  MX挂单失败: {e}")
        return False

def save_state(stock):
    today = datetime.now().strftime('%Y-%m-%d')
    state = {}
    if os.path.exists(STATE_FILE):
        try: state = json.load(open(STATE_FILE))
        except: pass
    if state.get('date') != today:
        state = {'date': today, 'stocks': []}
    state['stocks'].append(stock)
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w'), ensure_ascii=False, indent=2)

def scan():
    print(f"⚡ 竞价闪电扫描 {datetime.now().strftime('%H:%M:%S')}")
    stocks = get_premarket_lightning()
    if not stocks:
        print("  无符合条件标的")
        return
    
    print(f"  发现{len(stocks)}只,>7%竞价:")
    for s in stocks[:8]:
        tag = "🔴" if s['gap'] >= 9.5 else "🟠"
        print(f"  {tag} {s['name']}({s['code']}) ¥{s['price']:.2f} +{s['gap']:.1f}% 涨停{s['limit_up']:.2f}")
    
    # 挂单 ≤2只 (价高优先+量比优先)
    ordered = 0
    for s in stocks:
        if ordered >= 2: break
        if s['price'] < 3: continue  # 过滤垃圾低价
        
        qty = 100  # 默认一手
        if submit_mx_order(s['code'], s['name'], s['limit_up'], qty):
            print(f"  ✅ 挂单: {s['name']} {qty}股 @涨停¥{s['limit_up']:.2f}")
            ordered += 1
            save_state({
                "code": s['code'], "name": s['name'],
                "qty": qty, "price": s['limit_up'], "gap": s['gap']
            })
            alert("LIGHTNING", f"⚡ 竞价闪电 {s['name']}({s['code']}) +{s['gap']:.1f}% 挂涨停¥{s['limit_up']:.2f}")
        else:
            print(f"  ❌ 挂单失败: {s['name']}")

if __name__ == "__main__":
    scan()
