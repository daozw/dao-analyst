#!/usr/bin/env python3
"""打板·集合竞价 V3.0 — 竞价匹配度+挂单"""
import sys, os, json, urllib.request, ssl, subprocess
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ALERT_FILE = "/tmp/dao_trade_alerts.json"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "premarket.json")
HT_APIKEY = os.environ.get("HT_APIKEY", "ht_2dPFpTyi93kWDXZc5dlI2a7SFyfWCy3Y5cfcVLu2P")

MIN_GAP = 3.0; MAX_PRICE = 30

def get_premarket_stocks():
    try:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node=hs_a&symbol="
        req = urllib.request.Request(url, headers={"Referer":"https://finance.sina.com.cn","User-Agent":"Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        stocks = json.loads(raw)
        results = []
        for s in stocks:
            code = s.get("code","")
            if not (code.startswith(("60","00")) and not code.startswith("688")): continue
            if "ST" in s.get("name","") or "退" in s.get("name",""): continue
            op = float(s.get("open",0)); prev = float(s.get("settlement",0))
            if prev <= 0: continue
            gap = (op/prev-1)*100; price = float(s.get("trade",0))
            if gap >= MIN_GAP and price <= MAX_PRICE:
                results.append({"code":code,"name":s.get("name",""),"open":op,"price":price,
                    "gap":round(gap,2),"vol":float(s.get("volume",0)),
                    "amt":float(s.get("amount",0)),"high":float(s.get("high",0)),
                    "low":float(s.get("low",0)),"prev":prev,
                    "limit_up":round(prev*1.10,2)})
        results.sort(key=lambda x:-x["gap"])
        return results
    except: return []

def calc_match_score(s):
    score = 0
    gap = s["gap"]
    if gap >= 9: score += 30
    elif gap >= 7: score += 25
    elif gap >= 5: score += 18
    else: score += 10
    vol = s.get("vol",0)/10000
    if vol >= 10: score += 25
    elif vol >= 5: score += 20
    elif vol >= 2: score += 12
    else: score += 6
    amt = s.get("amt",0)/1e8
    if amt >= 1: score += 20
    elif amt >= 0.5: score += 15
    else: score += 8
    ratio = s["open"]/s["limit_up"] if s["limit_up"]>0 else 0
    if ratio >= 0.99: score += 15
    elif ratio >= 0.97: score += 12
    else: score += 8
    if s.get("high",0) > 0:
        amp = (s["high"]-s["low"])/s["open"]*100
        if amp < 1: score += 10
        elif amp < 2: score += 7
        else: score += 4
    return min(score, 100)

def submit_htsc_order(code, price, qty):
    """华泰挂单"""
    skill = os.path.expanduser("~/.openclaw-autoclaw/skills/a-share-paper-trading/a_share_paper_trading.py")
    env = {**os.environ, "HT_APIKEY": HT_APIKEY}
    cmd = [sys.executable, skill, "submitOrder", "--symbol", str(code),
           "--side", "buy", "--quantity", str(qty), "--price", str(price),
           "--exchange", "SZ" if code.startswith(("0","3","2")) else "SH"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=15)
    return json.loads(r.stdout) if r.stdout else {}

def scan():
    now = datetime.now()
    hour = now.hour*100 + now.minute
    if hour < 920 or hour > 925:
        if hour < 915: return "⏰ 集合竞价 9:15-9:25"
        return "⏰ 集合竞价已结束"
    
    stocks = get_premarket_stocks()
    if not stocks: return "📡 暂无高开候选"
    
    phase = "⏳可撤单" if hour < 920 else "🔒不可撤单" if hour < 925 else "📌定价完成"
    
    # 匹配度评分
    for s in stocks:
        s["score"] = calc_match_score(s)
    stocks.sort(key=lambda x:-x["score"])
    
    lines = [f"🔔 集合竞价 {now.strftime('%H:%M')} ({phase})"]
    lines.append(f"   高开≥{MIN_GAP}% ≤¥{MAX_PRICE}: {len(stocks)}只")
    
    # 极强+强势
    top = [s for s in stocks if s["score"] >= 70]
    if top:
        lines.append(f"\n{'─'*45}")
        for s in top[:5]:
            grade = "💎" if s["score"]>=85 else "🥇"
            lines.append(f"  {grade} {s['name']}({s['code']}) {s['score']}分 +{s['gap']:.1f}%")
            lines.append(f"    开¥{s['open']:.2f} 涨停¥{s['limit_up']:.2f} 量{s.get('vol',0)/10000:.1f}万手")
    
    # 09:25 定价后挂单
    if hour >= 925 and top:
        lines.append(f"\n📝 挂单(涨停价排队):")
        orders_placed = 0
        for s in top[:3]:
            if orders_placed >= 2: break  # 每日≤2只
            qty = min(500, int(10000 / s["limit_up"] / 100) * 100)
            if qty < 100: continue
            resp = submit_htsc_order(s["code"], s["limit_up"], qty)
            if resp.get("ok"):
                lines.append(f"  ✅ {s['name']} {qty}股 @涨停¥{s['limit_up']:.2f}")
                orders_placed += 1
                
                # 通知
                alerts = []
                if os.path.exists(ALERT_FILE):
                    try: alerts = json.load(open(ALERT_FILE))
                    except: pass
                alerts.append({
                    "time": now.strftime("%H:%M:%S"), "action": "AUCTION_ORDER",
                    "code": s["code"], "name": s["name"],
                    "message": f"🔔 竞价挂单 {s['name']}({s['code']}) {qty}股 @涨停¥{s['limit_up']:.2f}",
                    "sent": False
                })
                with open(ALERT_FILE, "w") as f:
                    json.dump(alerts, f, ensure_ascii=False, indent=2)
            else:
                lines.append(f"  ❌ {s['name']} 挂单失败")
    
    # 保存状态
    state = {"date": now.strftime("%Y-%m-%d"), "top_codes": [s["code"] for s in top[:5]]}
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    return "\n".join(lines)

if __name__ == "__main__":
    print(scan())
