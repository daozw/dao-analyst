#!/usr/bin/env python3
"""
🛡️ 止损守护进程 — stop_loss_guard.py
每15分钟扫描持仓，超-5%自动止损卖出。
解决连续3次进化报告指出的"止损执行缺口"问题。

用法: python3 stop_loss_guard.py [--dry-run] [--once]
  --dry-run  仅检查不执行
  --once     运行一次后退出(默认循环模式)
"""

import json
import os
import sys
import time
from datetime import datetime

# ========== 配置 ==========
STOP_LOSS_PCT = -5.0
HARD_STOP_PCT = -7.0
CHECK_INTERVAL = 900
POSITIONS_FILE = os.path.expanduser("~/dao-analyst/data/real_positions.json")
TRADE_LOG_FILE = os.path.expanduser("~/dao-analyst/data/trade_log.json")
GUARD_LOG_FILE = os.path.expanduser("~/dao-analyst/data/stop_loss_guard.log")
MAX_POSITIONS = 8
MAX_PER_STOCK = 3000

VENV_PYTHON = "/Users/sound/quant-research/daily_stock_analysis/.venv/bin/python3"
PAPER_TRADER = os.path.expanduser("~/dao-analyst/pipeline/paper_trader.py")


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(GUARD_LOG_FILE, "a") as f:
        f.write(line + "\n")


def is_trading_time():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    from datetime import time as ttime
    return (ttime(9, 30) <= t <= ttime(11, 30)) or (ttime(13, 0) <= t <= ttime(14, 57))


def get_positions():
    """优先MX API实时持仓，fallback本地文件"""
    try:
        sys.path.insert(0, os.path.expanduser('~/dao-analyst'))
        from pipeline.autotrade import get_mx_positions
        mx_pos, total, _ = get_mx_positions()
        if mx_pos:
            result = []
            for code, p in mx_pos.items():
                result.append({
                    'code': code, 'name': p['name'],
                    'qty': p['qty'], 'cost': p['cost'],
                    'account': p.get('account', 'MX')
                })
            return result
    except Exception as e:
        log(f"MX API failed, fallback to file: {e}")
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE) as f:
        data = json.load(f)
    return data.get("positions", [])


def get_prices_from_log(codes):
    prices = {}
    try:
        if os.path.exists(TRADE_LOG_FILE):
            with open(TRADE_LOG_FILE) as f:
                entries = json.load(f)
            for entry in reversed(entries):
                c = entry.get("code", "")
                if c in codes and c not in prices and entry.get("price"):
                    prices[c] = entry["price"]
                if len(prices) == len(codes):
                    break
    except Exception as e:
        log(f"⚠️ 价格获取失败: {e}")
    return prices


def execute_sell(code, name, quantity, price, reason):
    import subprocess
    try:
        script = f"""
import subprocess, sys
result = subprocess.run([
    '{VENV_PYTHON}', '{PAPER_TRADER}',
    '--stock-code', '{code}',
    '--direction', 'sell',
    '--quantity', '{quantity}',
    '--price', '{price}'
], capture_output=True, text=True, timeout=30)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
sys.exit(result.returncode)
"""
        result = subprocess.run(
            [VENV_PYTHON, "-c", script],
            capture_output=True, text=True, timeout=35
        )
        return {"ok": result.returncode == 0, "output": result.stdout, "error": result.stderr}
    except Exception as e:
        return {"ok": False, "output": "", "error": str(e)}


def check_and_stop(dry_run=False):
    positions = get_positions()
    if not positions:
        log("📭 当前空仓，无需检查")
        return []

    codes = [p.get("code", "") for p in positions]
    current_prices = get_prices_from_log(codes)
    alerts = []

    for pos in positions:
        code = pos.get("code", "?")
        name = pos.get("name", code)
        cost = pos.get("cost", pos.get("buy_price", 0))
        quantity = pos.get("quantity", pos.get("volume", 0))
        current = current_prices.get(code, pos.get("last_price", cost))

        if cost <= 0 or quantity <= 0:
            continue

        pnl_pct = (current - cost) / cost * 100

        if pnl_pct <= HARD_STOP_PCT:
            level = "🔴硬止损"
            reason = f"跌幅{pnl_pct:.1f}% 触发-7%硬止损"
            action_needed = True
        elif pnl_pct <= STOP_LOSS_PCT:
            level = "⚠️固定止损"
            reason = f"跌幅{pnl_pct:.1f}% 触发-5%止损"
            action_needed = True
        else:
            action_needed = False

        status = f"{level if action_needed else '✅'}"
        log(f"{status} {name}({code}) 成本¥{cost:.2f} 现价¥{current:.2f} 盈亏{pnl_pct:+.1f}% {'→'+reason if action_needed else ''}")

        if action_needed:
            alerts.append({
                "code": code, "name": name, "cost": cost,
                "current": current, "quantity": quantity,
                "pnl_pct": pnl_pct, "reason": reason, "level": level
            })

            if not dry_run:
                log(f"🚨 执行止损: {name}({code}) x{quantity} @{current:.2f}")
                result = execute_sell(code, name, quantity, str(current), reason)
                if result["ok"]:
                    log(f"✅ 止损委托成功: {name}({code})")
                    log_trade = {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "action": "STOP_SELL",
                        "code": code,
                        "name": name,
                        "price": current,
                        "quantity": quantity,
                        "amount": current * quantity,
                        "result": f"🛡️止损守护: {reason}",
                        "timestamp": datetime.now().isoformat()
                    }
                    try:
                        with open(TRADE_LOG_FILE) as f:
                            tl = json.load(f)
                        tl.append(log_trade)
                        with open(TRADE_LOG_FILE, "w") as f:
                            json.dump(tl, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                else:
                    log(f"❌ 止损失败: {name}({code}) → {result.get('error','unknown')}")
            else:
                log(f"🔍 [DRY-RUN] 将卖出: {name}({code}) x{quantity}")

    if len(positions) > MAX_POSITIONS:
        log(f"⚠️ 持仓数{len(positions)}>{MAX_POSITIONS}上限")

    return alerts


def main():
    dry_run = "--dry-run" in sys.argv
    once = "--once" in sys.argv

    log(f"🛡️ 止损守护进程启动 (dry_run={dry_run}, once={once})")
    log(f"   止损: -5%固定 / -7%硬止损 | 持仓上限: {MAX_POSITIONS}只")

    while True:
        if is_trading_time() or dry_run:
            try:
                alerts = check_and_stop(dry_run=dry_run)
                if alerts:
                    log(f"⚠️ 本次触发{len(alerts)}条止损")
                else:
                    log("✅ 持仓正常")
            except Exception as e:
                log(f"❌ 异常: {e}")

        if once:
            log("🏁 单次检查完成")
            break

        log(f"⏳ 等待{CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
