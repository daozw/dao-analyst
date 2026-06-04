#!/usr/bin/env python3
"""
mx-moni 模拟交易桥接 V1.0
连接策略系统 → 妙想模拟交易 → 完成分析→执行闭环
"""
import subprocess, json, os, sys
from datetime import datetime

MX_APIKEY = os.environ.get("MX_APIKEY", "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8")
API_URL = "https://mkapi2.dfcfs.com/finskillshub"
MONI_SCRIPT = os.path.expanduser("~/.openclaw-autoclaw/skills/mx-moni/mx_moni.py")

def run_moni(command):
    """调用 mx-moni 脚本"""
    env = {**os.environ, "MX_APIKEY": MX_APIKEY}
    r = subprocess.run(
        ["python3", MONI_SCRIPT, command],
        capture_output=True, text=True, env=env, timeout=15
    )
    return r.stdout.strip()

def curl_moni(endpoint, data):
    """直接 curl 调用妙想API"""
    import urllib.request, urllib.error
    url = f"{API_URL}/api/claw/mockTrading/{endpoint}"
    headers = {"apikey": MX_APIKEY, "Content-Type": "application/json"}
    
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "msg": e.read().decode()}
    except Exception as e:
        return {"error": str(e)}

# ═══════════════════════════════════
# 账户查询
# ═══════════════════════════════════
def get_balance():
    """查询账户资金"""
    return curl_moni("balance", {"moneyUnit": 1})

def get_positions():
    """查询持仓"""
    return curl_moni("positions", {"moneyUnit": 1})

def get_orders(status=0):
    """查询委托"""
    return curl_moni("orders", {"fltOrderDrt": 0, "fltOrderStatus": status})

# ═══════════════════════════════════
# 交易执行
# ═══════════════════════════════════
def buy_stock(code, price, quantity, market_price=False):
    """
    买入股票
    code: 6位代码如 600027
    price: 委托价格
    quantity: 数量(100的倍数)
    market_price: True=市价买入
    """
    return curl_moni("trade", {
        "type": "buy",
        "stockCode": code,
        "price": price,
        "quantity": quantity,
        "useMarketPrice": market_price
    })

def sell_stock(code, price, quantity, market_price=False):
    """卖出股票"""
    return curl_moni("trade", {
        "type": "sell",
        "stockCode": code,
        "price": price,
        "quantity": quantity,
        "useMarketPrice": market_price
    })

def cancel_order(order_id, code):
    """撤单"""
    return curl_moni("cancel", {
        "type": "order",
        "orderId": order_id,
        "stockCode": code
    })

def cancel_all():
    """一键撤单"""
    return curl_moni("cancel", {"type": "all"})

# ═══════════════════════════════════
# 策略集成
# ═══════════════════════════════════
def execute_signal(signal, max_amount=2000):
    """
    根据策略信号执行交易
    
    signal: {"ticker": "600027", "action": "BUY", "price": 5.50, "reason": "..."}
    max_amount: 单笔最大金额
    """
    ticker = signal.get("ticker", "")
    action = signal.get("action", "")
    price = signal.get("price", 0)
    reason = signal.get("reason", "")
    
    if action not in ("BUY", "SELL"):
        return {"error": f"不支持的操作: {action}"}
    
    # 硬性风险上限: 2万
    RISK_CAP = 20000
    
    # 检查账户
    bal = get_balance()
    if bal.get("code") != "200" and bal.get("rc") != 0:
        return {"error": f"账户查询失败: {bal}"}
    
    if action == "BUY":
        effective_amount = min(max_amount, RISK_CAP)
        available = bal.get("availableCash", 0) if bal_data else 0
        
        # 检查当前总持仓
        pos_data = get_positions()
        pos_data_inner = pos_data.get("data", pos_data)
        current_holdings = pos_data_inner.get("posList", [])
        current_value = sum(h.get("lastPrice", 0) * h.get("count", 0) for h in current_holdings)
        
        if current_value >= RISK_CAP:
            return {"error": f"总持仓{current_value:,.0f}已达2万上限", "current": current_value, "limit": RISK_CAP}
        
        remaining = RISK_CAP - current_value
        if effective_amount > remaining:
            effective_amount = remaining
        
        qty = max(100, int(effective_amount / price / 100) * 100)
        if qty * price > remaining:
            qty = max(100, int(remaining / price / 100) * 100)
        result = buy_stock(ticker, price, qty)
        
        return {
            "action": "BUY",
            "ticker": ticker,
            "price": price,
            "quantity": qty,
            "amount": qty * price,
            "reason": reason,
            "result": result
        }
    
    elif action == "SELL":
        # 查持仓
        pos = get_positions()
        holdings = pos.get("positions", []) if pos.get("rc") == 0 else []
        
        target = None
        for h in holdings:
            if h.get("secCode") == ticker:
                target = h
                break
        
        if not target:
            return {"error": f"未持仓{ticker}", "ticker": ticker}
        
        qty = target.get("count", 0)
        result = sell_stock(ticker, price, qty)
        
        return {
            "action": "SELL",
            "ticker": ticker,
            "price": price,
            "quantity": qty,
            "amount": qty * price,
            "reason": reason,
            "result": result
        }

def batch_execute(signals, max_amount=2000):
    """批量执行信号"""
    results = []
    for sig in signals:
        r = execute_signal(sig, max_amount)
        results.append(r)
        print(f"  {r.get('action','?')} {r.get('ticker','?')}: {r.get('reason', r.get('error','?'))[:40]}")
    return results

# ═══════════════════════════════════
# 账户仪表盘
# ═══════════════════════════════════
def dashboard():
    """交易仪表盘"""
    print("=" * 55)
    print("  📊 mx-moni 模拟交易仪表盘")
    print("=" * 55)
    
    # 资金
    bal = get_balance()
    bal_data = bal.get("data", bal)
    bal_data = bal.get("data", bal)
    if bal.get("code") == "200" or bal.get("rc") == 0:
        total = bal_data.get("totalAssets", 0)
        available = bal_data.get("availBalance", 0)
        pnl = bal_data.get("totalProfit", 0)
        pnl_pct = bal_data.get("totalPosPct", 0)
        print(f"\n💰 账户资金")
        print(f"  总资产:  ¥{total:,.2f}")
        print(f"  可用:    ¥{available:,.2f}")
        print(f"  盈亏:    {pnl:+,.2f}  ({pnl_pct:+.2f}%)")
    else:
        print(f"\n💰 资金查询失败: {bal}")
    
    # 持仓
    pos = get_positions()
    pos_data = pos.get("data", pos)
    if pos.get("code") == "200" or pos.get("rc") == 0:
        holdings = pos_data.get("posList", pos.get("positions", []))
        print(f"\n📦 持仓 ({len(holdings)}只)")
        if holdings:
            print(f"  {'代码':<8} {'名称':<8} {'数量':>6} {'成本':>8} {'现价':>8} {'盈亏':>10}")
            for h in holdings:
                code = h.get("secCode", "")
                name = h.get("secName", "")[:6]
                qty = h.get("count", 0)
                cost = h.get("costPrice", 0)
                price = h.get("lastPrice", 0)
                pnl = h.get("profit", 0)
                print(f"  {code:<8} {name:<8} {qty:>6} {cost:>8.2f} {price:>8.2f} {pnl:>+10.2f}")
        else:
            print("  (空仓)")
    else:
        print(f"\n📦 持仓查询失败: {pos}")
    
    # 委托
    ords = get_orders()
    ords_data = ords.get("data", ords)
    if ords.get("code") == "200" or ords.get("rc") == 0:
        orders = ords_data.get("orders", [])
        pending = [o for o in orders if o.get("status") in (1, 2)]  # 未报/已报
        print(f"\n📋 委托 ({len(pending)}笔待成交)")
        if pending:
            for o in pending[:5]:
                print(f"  {o.get('drt','?')} {o.get('secCode','')} "
                      f"{o.get('count',0)}股 @{o.get('price',0)}")
    else:
        print(f"\n📋 委托查询失败: {ords}")

# ═══════════════════════════════════
# CLI
# ═══════════════════════════════════
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dashboard"
    
    if cmd == "dashboard":
        dashboard()
    
    elif cmd == "balance":
        print(json.dumps(get_balance(), ensure_ascii=False, indent=2))
    
    elif cmd == "positions":
        print(json.dumps(get_positions(), ensure_ascii=False, indent=2))
    
    elif cmd == "orders":
        print(json.dumps(get_orders(), ensure_ascii=False, indent=2))
    
    elif cmd == "buy":
        if len(sys.argv) < 5:
            print("用法: python3 mx_bridge.py buy <code> <price> <qty> [--market]")
        else:
            code, price, qty = sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
            market = "--market" in sys.argv
            r = buy_stock(code, price, qty, market)
            print(json.dumps(r, ensure_ascii=False, indent=2))
    
    elif cmd == "sell":
        if len(sys.argv) < 5:
            print("用法: python3 mx_bridge.py sell <code> <price> <qty> [--market]")
        else:
            code, price, qty = sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
            market = "--market" in sys.argv
            r = sell_stock(code, price, qty, market)
            print(json.dumps(r, ensure_ascii=False, indent=2))
    
    elif cmd == "cancel":
        if len(sys.argv) < 4:
            print("用法: python3 mx_bridge.py cancel <order_id> <code>")
            print("       python3 mx_bridge.py cancel --all")
        elif sys.argv[2] == "--all":
            print(json.dumps(cancel_all(), ensure_ascii=False, indent=2))
        else:
            r = cancel_order(sys.argv[2], sys.argv[3])
            print(json.dumps(r, ensure_ascii=False, indent=2))
    
    elif cmd == "signal":
        # 示例信号
        sig = {
            "ticker": sys.argv[2] if len(sys.argv) > 2 else "600027",
            "action": sys.argv[3] if len(sys.argv) > 3 else "BUY",
            "price": float(sys.argv[4]) if len(sys.argv) > 4 else 5.50,
            "reason": "策略V3.0信号"
        }
        r = execute_signal(sig)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    
    else:
        print("""
📊 mx-moni 模拟交易桥接
  dashboard     账户仪表盘
  balance       查询资金
  positions     查询持仓
  orders        查询委托
  buy <code> <price> <qty> [--market]   买入
  sell <code> <price> <qty> [--market]  卖出
  cancel <order_id> <code>|--all        撤单
  signal <code> <BUY|SELL> <price>      策略信号执行
""")
