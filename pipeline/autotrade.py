# DAO分析师 V3.3 — 3万核心作战系统
#!/usr/bin/env python3
"""自动交易 — 600元风险公式 + 分阶止盈 + MA5跟踪"""
import sys, os, json, urllib.request, ssl
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST = os.path.join(BASE, "data", "watchlist.json")
DAILY_STATE = os.path.join(BASE, "data", "state", "band.json")
ssl._create_default_https_context = ssl._create_unverified_context

MX_KEY = os.environ.get("MX_APIKEY", "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8")
MX_API = "https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading"
MAX_STOCKS_PER_DAY = 3
CORE_CAP = 20000       # 核心作战仓
GUERRILLA_CAP = 10000  # 机动游击仓
TOTAL_CAP = 30000      # 总资金
MAX_LOSS = 600         # 单笔最大亏损


def _mx_call(endpoint, data=None):
    if data is None: data = {}
    req = urllib.request.Request(f"{MX_API}/{endpoint}", data=json.dumps(data).encode(),
        headers={"apikey": MX_KEY, "Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def get_mx_positions():
    resp = _mx_call("positions")
    data = resp.get("data", resp)
    pl = data.get("posList", [])
    pos, tv, tp = {}, 0, 0
    for p in pl:
        code = p["secCode"]; qty = p["count"]; cost = p["costPrice"]/(10**p.get("costPriceDec",3))
        value = p["value"]/1000; profit = p["profit"]/1000
        tv += value; tp += profit
        pos[code] = {"name": p.get("secName",""), "qty": qty, "cost": cost, "value": value,
                     "profit": profit, "profit_pct": p.get("profitPct",0)}
    return pos, tv, tp


def load_daily_state():
    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(DAILY_STATE):
        s = json.load(open(DAILY_STATE))
        if s.get("date") == today: return s
    return {"date": today, "stocks": [], "total_spent": 0, "buy_count": 0}


def save_daily_state(s):
    os.makedirs(os.path.dirname(DAILY_STATE), exist_ok=True)
    json.dump(s, open(DAILY_STATE, "w"), ensure_ascii=False, indent=2)


def calc_shares(entry_price, stop_price):
    """仓位公式: 趋势600/震荡400/熊市0"""
    regime = get_market_regime()
    if regime == "BEAR": return 0  # 熊市不交易
    risk = 600 if regime == "TREND" else 400  # 震荡降低风险
    if entry_price <= stop_price: return 0
    shares = int(risk / (entry_price - stop_price) / 100) * 100
    if shares < 100: return 0
    value = shares * entry_price
    if value > CORE_CAP: shares = int(CORE_CAP / entry_price / 100) * 100
    if shares * entry_price < 5000: return 0
    return shares


def _exec_trade(action, code, name, price, qty, dry_run=True):
    value = price * qty
    if dry_run:
        return True, f"📋 {action} {name}({code}) {qty}股 @¥{price:.2f} = ¥{value:,.0f}"
    data = json.dumps({"type": "buy" if action=="BUY" else "sell", "stockCode": code,
                        "price": price, "quantity": qty, "useMarketPrice": False}).encode()
    req = urllib.request.Request(f"{MX_API}/trade", data=data,
        headers={"apikey": MX_KEY, "Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    ok = resp.get("code") == "200"
    from pipeline.trade_notify import notify_trade
    notify_trade(action, code, name, price, qty, "成功" if ok else resp.get("message","失败"))
    notify_trade(action, code, name, price, qty, "成功" if ok else resp.get("message","失败"))
    return ok, f"{'✅' if ok else '❌'} {action} {name}({code}) {qty}股 @¥{price:.2f} = ¥{value:,.0f}"


def get_stop_stages(entry, stop, current):
    """分阶止盈: 趋势慢卖/震荡快卖"""
    regime = get_market_regime()
    profit_pct = (current / entry - 1) * 100
    
    if regime == "TREND":
        # 趋势: 让利润奔跑
        if profit_pct >= 15: return "MA5跟踪", "趋势强,收盘破MA5清仓"
        elif profit_pct >= 8: return "卖半仓", f"卖50% 剩余保本"
        elif profit_pct >= 2: return "保本上移", f"止损→¥{entry:.2f}"
    elif regime == "CHOP":
        # 震荡: 快进快出
        if profit_pct >= 8: return "清仓", f"震荡市不贪,落袋+{profit_pct:.0f}%"
        elif profit_pct >= 3: return "卖半仓", f"卖50%锁利"
        elif profit_pct >= 1: return "保本上移", f"止损→¥{entry:.2f}"
    else:
        # 熊市不交易
        return "不交易", "熊市"
    
    return "持有", f"止损¥{stop:.2f}"


def get_market_regime():
    """市场状态判断: TREND=趋势, CHOP=震荡, BEAR=熊市"""
    try:
        from market_sentiment import get_market_sentiment
        s, _ = get_market_sentiment()
        if s == "🟢积极": return "TREND"
        elif s == "🟡中性": return "CHOP"
        elif s == "🔴谨慎": return "BEAR"
    except: pass
    return "TREND"  # 默认趋势


def auto_trade(dry_run=True):
    from pipeline.fetcher import fetch
    from pipeline.signals import analyze
    
    wl = json.load(open(WATCHLIST))
    band = wl.get("groups", {}).get("band", {}).get("stocks", [])
    state = load_daily_state()
    
    mx_pos, mx_tv, mx_tp = {}, 0, 0
    dyn_cap = CORE_CAP
    if not dry_run:
        try: mx_pos, mx_tv, mx_tp = get_mx_positions(); dyn_cap = CORE_CAP + mx_tp
        except: pass
    
    used = mx_tv if mx_tv > state["total_spent"] else state["total_spent"]
    remaining = dyn_cap - used if not dry_run else dyn_cap - state["total_spent"]
    
    lines = [f"🤖 3万作战系统 {'[模拟]' if dry_run else '[实盘]'}"]
    lines.append(f"  核心仓¥{CORE_CAP:,} | 单笔风险¥600 | 分阶止盈")
    lines.append(f"  今日 {state['buy_count']}/{MAX_STOCKS_PER_DAY}只 | 剩余¥{remaining:,.0f}")
    lines.append("")
    
    executed = []
    bought = {st["code"] for st in state["stocks"]}
    
    for s in band:
        code = s["code"]; name = s["name"]
        
        if state["buy_count"] >= MAX_STOCKS_PER_DAY:
            lines.append(f"  ⏭️ {name} (今日{MAX_STOCKS_PER_DAY}只满)"); continue
        if code in bought:
            lines.append(f"  ⏭️ {name} (今日已买)"); continue
        if not dry_run and code in mx_pos:
            lines.append(f"  ⏭️ {name} (已持{mx_pos[code]['qty']}股)"); continue
        
        d = fetch(code, use_cache=False)
        if "error" in d: lines.append(f"  ❌ {name} 数据错误"); continue
        
        a = analyze(d); sig = a["g"]; chg = d["chg"]; price = d["price"]; pr = a["prices"]
        
        if sig < 3: lines.append(f"  ⏭️ {name} (信号{sig}/6)"); continue
        
        # 涨跌停保护
        prev_close = d.get("prev_close", price)
        limit_up = round(prev_close * 1.10, 2)
        limit_down = round(prev_close * 0.90, 2)
        if price >= limit_up:
            lines.append(f"  ⏭️ {name} (已涨停不再追)"); continue
        if price <= limit_down:
            lines.append(f"  ⏭️ {name} (跌停不抄底)"); continue
        if chg >= 5: lines.append(f"  ⏭️ {name} (涨幅{chg:+.1f}%追高)"); continue
        if chg <= -2: lines.append(f"  ⏭️ {name} (跌幅{chg:+.1f}%)"); continue
        
        min_cost = price * 100
        if remaining < min_cost:
            lines.append(f"  ⏭️ {name} (剩余¥{remaining:,.0f}不够1手)"); continue
        
        shares = calc_shares(price, pr["stop_loss"])
        if shares < 100:
            lines.append(f"  ⏭️ {name} (止损空间过大,放弃)"); continue
        
        value = shares * price
        risk = shares * (price - pr["stop_loss"])
        
        ok, msg = _exec_trade("BUY", code, name, price, shares, dry_run)
        lines.append(f"  {msg} {sig}/6 风险¥{risk:,.0f}")
        lines.append(f"     止损¥{pr['stop_loss']:.2f} 止盈¥{pr['take_profit_1']:.2f}")
        
        # 分阶计划
        stage, action = get_stop_stages(price, pr["stop_loss"], price)
        lines.append(f"     +1%→保本 +5%→卖半 +10%→MA5跟踪")
        
        if ok:
            executed.append({"code": code, "name": name, "shares": shares, "price": price, "value": value})
            state["stocks"].append({"code": code, "name": name, "shares": shares, "price": price, "value": value})
            state["buy_count"] += 1; state["total_spent"] += value
            bought.add(code); remaining -= value
    

    # T+1检查: 当天买的不能卖
    today_codes = {st["code"] for st in state["stocks"]}

    # 止盈止损检查
    if not dry_run and mx_pos:
        for code, pos in mx_pos.items():
            if code in today_codes:
                lines.append(f"  🔒 {pos['name']} T+1锁仓(今日买入)")
                continue
            d = fetch(code, use_cache=False)
            if "error" in d: continue
            a = analyze(d); price = d["price"]; pr = a["prices"]
            profit_pct = pos["profit_pct"]
            
            should = False; reason = ""
            entry = pos["cost"]
            
            if profit_pct <= -5: should = True; reason = f"止损{profit_pct:.0f}%"
            elif profit_pct >= 10: should = True; reason = f"大赚{profit_pct:.0f}%清仓"
            elif profit_pct >= 5: should = True; reason = f"小赚{profit_pct:.0f}%卖半仓"
            elif profit_pct >= 1:
                # 上移止损到成本价
                reason = f"微赚{profit_pct:.0f}%→保本"
                # No sell, just log
                lines.append(f"  🟢 {pos['name']} {reason}")
            
            if should and "卖半仓" in reason:
                sell_qty = max(100, pos["qty"] // 2 // 100 * 100)
                ok, msg = _exec_trade("SELL", code, pos["name"], price, sell_qty, dry_run)
                lines.append(f"  {msg} ({reason})")
                if ok: remaining += sell_qty * price
            elif should:
                ok, msg = _exec_trade("SELL", code, pos["name"], price, pos["qty"], dry_run)
                lines.append(f"  {msg} ({reason})")
                if ok: remaining += pos["qty"] * price
    
    save_daily_state(state)
    if executed:
        lines.append(f"\n💰 今日买入 {len(executed)}只 ¥{sum(e['value'] for e in executed):,.0f}")
    else:
        lines.append(f"\n💰 今日无买入")
    return "\n".join(lines), executed


if __name__ == "__main__":
    dry = "--real" not in sys.argv
    result, _ = auto_trade(dry_run=dry)
    print(result)
