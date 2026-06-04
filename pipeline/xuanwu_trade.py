#!/usr/bin/env python3
"""玄武·交易官 — 华泰证券独立交易系统 V1.0"""
import sys, os, json, subprocess
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_STATE = os.path.join(BASE, "data", "state", "board_trade.json")
WATCHLIST = os.path.join(BASE, "data", "watchlist.json")

# HTSC unified via trader.py
MAX_STOCKS_PER_DAY = 3
BASE_CAPITAL = 10000  # 机动游击仓
SIGNAL_ALLOC = {6: 8000, 5: 6000, 4: 5000, 3: 3000}


def htsc_submit(action, code, price, qty):
    """提交华泰订单 — 自动选择模拟/实盘"""
    from trader import UnifiedTrader
    trader = UnifiedTrader()
    
    if action == "BUY":
        resp = trader.buy(code, price, qty)
    else:
        resp = trader.sell(code, price, qty)
    
    ok = resp.get("ok", False)
    return ok, resp


def htsc_query_positions():
    """查询华泰持仓"""
    from trader import UnifiedTrader
    trader = UnifiedTrader()
    resp = trader.positions()
    # 转换为兼容格式
    if resp.get("ok"):
        pos_list = resp.get("data", {}).get("posList", [])
        return {"ok": True, "data": {"posList": pos_list}}
    return resp


def load_daily_state():
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(DAILY_STATE):
        state = json.load(open(DAILY_STATE))
        if state.get("date") == today:
            return state
    return {"date": today, "stocks": [], "total_spent": 0, "buy_count": 0}


def save_daily_state(state):
    os.makedirs(os.path.dirname(DAILY_STATE), exist_ok=True)
    with open(DAILY_STATE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def htsc_trade(signals, dry_run=True):
    """
    华泰侧交易执行
    signals: [{"code": "000001", "name": "平安银行", "price": 12.50, "signal": 5, "shares": 400}, ...]
    """
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze

    state = load_daily_state()

    # 查询华泰持仓
    positions = {}
    total_value = 0
    if not dry_run:
        pos_resp = htsc_query_positions()
        pos_list = pos_resp.get("data", {}).get("posList", []) if pos_resp.get("ok") else []
        for p in pos_list:
            code = p.get("secCode", "")
            positions[code] = {
                "name": p.get("secName", ""),
                "qty": p.get("count", 0),
                "cost": p.get("costPrice", 0),
                "value": p.get("value", 0) / 1000,
            }
            total_value += positions[code]["value"]

    remaining_cap = BASE_CAPITAL - (total_value if total_value > state["total_spent"] else state["total_spent"])

    lines = [f"🐢 玄武·交易官 {'[模拟]' if dry_run else '[实盘]'} V1.0"]
    lines.append(f"  华泰资金 ¥{BASE_CAPITAL:,} | 已用 ¥{state['total_spent']:,} | 剩余 ¥{remaining_cap:,}")
    lines.append(f"  持仓 {len(positions)}只 | 今日已买 {state['buy_count']}/{MAX_STOCKS_PER_DAY}")
    lines.append("")

    if state["buy_count"] >= MAX_STOCKS_PER_DAY:
        lines.append("⛔ 今日额度用完")
        return "\n".join(lines), []

    executed = []

    for sig in signals:
        if state["buy_count"] >= MAX_STOCKS_PER_DAY:
            break

        code = sig["code"]
        name = sig["name"]
        signal_level = sig.get("signal", 3)

        # 已在华泰持仓，跳过
        if code in positions:
            lines.append(f"  ⏭ {name}({code}) 已有华泰持仓")
            continue

        # 验证实时行情
        d = fetch(code, use_cache=False)
        if "error" in d:
            lines.append(f"  ❌ {name}({code}) 行情获取失败")
            continue

        price = d["price"]
        chg = d["chg"]

        # 打板：允许追涨停（去掉追高保护）
        if chg > 9.8:  # 已封板不追
            lines.append(f"  🚫 {name}({code}) 已封板 排板等待")
            continue

        # 动态仓位分配
        alloc = SIGNAL_ALLOC.get(signal_level, 3000)
        if alloc > remaining_cap:
            alloc = int(remaining_cap * 0.8)

        qty = int(alloc / price / 100) * 100  # 整手
        if qty < 100:
            lines.append(f"  ⚠️ {name}({code}) 资金不足，跳过 (¥{price:.2f}, 需≥¥{price*100:.0f})")
            continue

        value = price * qty

        ok, resp = htsc_submit("BUY", code, price, qty)
        tag = "✅" if ok else "❌"
        lines.append(f"  {tag} BUY {name}({code}) {qty}股 @¥{price:.2f} = ¥{value:,.0f}")

        if ok:
            executed.append({"code": code, "name": name, "qty": qty, "price": price, "value": value})
            state["stocks"].append(sig)
            state["total_spent"] += value
            state["buy_count"] += 1
            remaining_cap -= value
        else:
            err = resp.get("error", resp.get("message", "未知错误"))
            lines.append(f"    错误: {err}")

    save_daily_state(state)

    if executed:
        lines.append(f"\n💰 华泰今日买入 {len(executed)}只 ¥{sum(e['value'] for e in executed):,.0f}")
    else:
        lines.append("\n💰 华泰今日无买入")

    return "\n".join(lines), executed


def xuanwu_clear_positions(dry_run=True):
    """华泰盘前清仓"""
    if dry_run:
        return "📋 华泰清仓 [模拟] — 如有持仓将执行止损/走弱检查"

    pos_resp = htsc_query_positions()
    if not pos_resp.get("ok"):
        return "❌ 华泰持仓查询失败"

    pos_list = pos_resp.get("data", {}).get("posList", [])
    if not pos_list:
        return "📦 华泰空仓"

    lines = ["🧹 玄武清仓", f"  华泰持仓 {len(pos_list)}只", ""]
    sold = []

    for p in pos_list:
        code = p.get("secCode", "")
        name = p.get("secName", "")
        qty = p.get("count", 0)
        profit_pct = p.get("profitPct", 0)

        from pipeline.fetcher import fetch
        from pipeline.signals import analyze
        d = fetch(code, use_cache=False)
        sig = 0
        price = 0
        if "error" not in d:
            a = analyze(d)
            sig = a["g"]
            price = d["price"]

        should_sell = False
        reason = ""
        if profit_pct <= -3:
            should_sell = True
            reason = f"亏损{profit_pct:.0f}%止损"
        elif sig < 2:
            should_sell = True
            reason = f"信号{sig}/6走弱"

        if should_sell and price > 0:
            ok, _ = htsc_submit("SELL", code, price, qty)
            lines.append(f"  {'✅' if ok else '❌'} SELL {code} {name} {qty}股 ({reason})")
            if ok:
                sold.append({"code": code, "name": name, "qty": qty, "price": price})
        else:
            lines.append(f"  ✅ HOLD {code} {name} {qty}股 盈亏{profit_pct:+.1f}% 信号{sig}/6")

    if sold:
        lines.append(f"\n💰 清仓 {len(sold)}只 回收 ¥{sum(s['price']*s['qty'] for s in sold):,.0f}")
    else:
        lines.append("\n✅ 无需清仓")
    return "\n".join(lines)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    dry_run = "--real" not in sys.argv

    if cmd == "query":
        resp = htsc_query_positions()
        print(json.dumps(resp, ensure_ascii=False, indent=2))
    elif cmd == "clear":
        print(xuanwu_clear_positions(dry_run=dry_run))
    elif cmd == "trade":
        # 从 stdin 读取信号
        signals_raw = sys.stdin.read().strip()
        if not signals_raw:
            print("❌ 无交易信号")
            sys.exit(1)
        signals = json.loads(signals_raw)
        result, _ = htsc_trade(signals, dry_run=dry_run)
        print(result)
    elif cmd == "help":
        print("玄武·交易官 V1.0")
        print("  python xuanwu_trade.py query       查询华泰持仓")
        print("  python xuanwu_trade.py clear        盘前清仓 [--real]")
        print("  python xuanwu_trade.py trade        执行交易 [--real] (从stdin读取信号JSON)")
