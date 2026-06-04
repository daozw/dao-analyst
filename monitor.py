#!/usr/bin/env python3
"""A股实时监控 + 智能告警系统"""

import os, sys, json, time, subprocess
from datetime import datetime
from pathlib import Path

MONITOR_DIR = Path.home() / "dao-analyst" / "monitor"
MONITOR_DIR.mkdir(parents=True, exist_ok=True)

# 监控配置
WATCHLIST_FILE = MONITOR_DIR / "watchlist.json"
ALERTS_FILE = MONITOR_DIR / "alerts.json"
LOG_FILE = MONITOR_DIR / "monitor.log"

ANALYZE_SCRIPT = Path.home() / ".openclaw-autoclaw/skills/a-stock-analysis/scripts/analyze.py"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_price(ticker):
    """获取实时价格"""
    try:
        r = subprocess.run(
            ["python3", str(ANALYZE_SCRIPT), ticker, "--json"],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(r.stdout)[0]
        rt = data["realtime"]
        return {
            "ticker": ticker,
            "name": data["name"],
            "price": rt["price"],
            "change_pct": rt["change_pct"],
            "volume": rt["volume"],
            "amount": rt["amount"],
            "high": rt["high"],
            "low": rt["low"],
            "time": datetime.now().isoformat()
        }
    except Exception as e:
        log(f"❌ {ticker} 获取失败: {e}")
        return None

def load_watchlist():
    """加载监控列表"""
    if WATCHLIST_FILE.exists():
        return json.loads(WATCHLIST_FILE.read_text())
    return {"stocks": [], "alerts": {}}

def save_watchlist(wl):
    WATCHLIST_FILE.write_text(json.dumps(wl, indent=2, ensure_ascii=False))

def check_alerts(price_data, alerts_config):
    """检查告警条件"""
    triggered = []
    ticker = price_data["ticker"]
    if ticker not in alerts_config:
        return triggered
    
    cfg = alerts_config[ticker]
    price = price_data["price"]
    
    # 价格上破
    if "above" in cfg and price >= cfg["above"]:
        triggered.append(f"🔴 {price_data['name']} 突破 {cfg['above']}，现价 {price}")
    
    # 价格下破
    if "below" in cfg and price <= cfg["below"]:
        triggered.append(f"🟢 {price_data['name']} 跌破 {cfg['below']}，现价 {price}")
    
    # 涨跌幅
    if "change_up" in cfg and price_data["change_pct"] >= cfg["change_up"]:
        triggered.append(f"📈 {price_data['name']} 涨幅 {price_data['change_pct']:.1f}%")
    
    if "change_down" in cfg and price_data["change_pct"] <= -cfg["change_down"]:
        triggered.append(f"📉 {price_data['name']} 跌幅 {price_data['change_pct']:.1f}%")
    
    return triggered

def run_check():
    """执行一轮监控"""
    wl = load_watchlist()
    if not wl["stocks"]:
        log("⚠️ 监控列表为空")
        return []
    
    log(f"📊 扫描 {len(wl['stocks'])} 只股票...")
    triggered = []
    
    for ticker in wl["stocks"]:
        data = get_price(ticker)
        if data:
            pct = data["change_pct"]
            arrow = "🔺" if pct > 0 else "🔻" if pct < 0 else "➖"
            log(f"  {arrow} {data['name']}({ticker}): {data['price']:.2f} ({pct:+.2f}%)")
            
            # 检查告警
            alerts = check_alerts(data, wl.get("alerts", {}))
            triggered.extend(alerts)
    
    return triggered

# CLI
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    
    if cmd == "check":
        alerts = run_check()
        if alerts:
            print("\n⚠️ 触发告警:")
            for a in alerts:
                print(f"  {a}")
        else:
            print("\n✅ 无告警触发")
    
    elif cmd == "add":
        ticker = sys.argv[2]
        wl = load_watchlist()
        if ticker not in wl["stocks"]:
            wl["stocks"].append(ticker)
            save_watchlist(wl)
            log(f"✅ 添加 {ticker}")
    
    elif cmd == "remove":
        ticker = sys.argv[2]
        wl = load_watchlist()
        if ticker in wl["stocks"]:
            wl["stocks"].remove(ticker)
            save_watchlist(wl)
            log(f"✅ 移除 {ticker}")
    
    elif cmd == "list":
        wl = load_watchlist()
        print(f"📋 监控列表 ({len(wl['stocks'])}只):")
        for t in wl["stocks"]:
            print(f"  {t}")
    
    elif cmd == "alert":
        ticker = sys.argv[2]
        wl = load_watchlist()
        if "alerts" not in wl:
            wl["alerts"] = {}
        
        cfg = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--above":
                cfg["above"] = float(sys.argv[i+1]); i += 2
            elif sys.argv[i] == "--below":
                cfg["below"] = float(sys.argv[i+1]); i += 2
            elif sys.argv[i] == "--change-up":
                cfg["change_up"] = float(sys.argv[i+1]); i += 2
            elif sys.argv[i] == "--change-down":
                cfg["change_down"] = float(sys.argv[i+1]); i += 2
            else:
                i += 1
        
        wl["alerts"][ticker] = cfg
        save_watchlist(wl)
        log(f"✅ {ticker} 告警已设置: {cfg}")
    
    elif cmd == "loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        log(f"🔄 开始循环监控 (间隔 {interval}s)")
        try:
            while True:
                run_check()
                time.sleep(interval)
        except KeyboardInterrupt:
            log("⏹ 监控停止")
