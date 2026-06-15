#!/usr/bin/env python3
"""策略冻结守卫 V1.0 — 连亏3天→策略冻结24h + 时间止损"""
import json, os, time, fcntl
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FREEZE_FILE = os.path.join(BASE, "data", "state", "freeze_state.json")
P_L_FILE = os.path.join(BASE, "data", "state", "daily_pnl.json")
MAX_CONSECUTIVE_LOSS_DAYS = 3
FREEZE_DURATION_HOURS = 24
TIME_STOP_DAYS = 3  # 持仓>3天未盈利→强制平仓

def _atomic_read(path, default=None):
    try:
        with open(path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}

def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# ── 每日盈亏记录 ──
def record_daily_pnl(date_str=None, pnl=0, trade_count=0):
    """记录每日盈亏"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    records = _atomic_read(P_L_FILE, [])
    # 更新或追加当日记录
    found = False
    for r in records:
        if r.get("date") == date_str:
            r["pnl"] = round(r.get("pnl", 0) + pnl, 2)
            r["trades"] = r.get("trades", 0) + trade_count
            r["updated"] = datetime.now().isoformat()
            found = True
            break
    if not found:
        records.append({
            "date": date_str, "pnl": round(pnl, 2), "trades": trade_count,
            "updated": datetime.now().isoformat()
        })
    
    # 只保留最近60天
    records = records[-60:]
    _atomic_write(P_L_FILE, records)

def get_recent_pnl(days=10):
    """获取最近N天盈亏"""
    records = _atomic_read(P_L_FILE, [])
    return sorted(records, key=lambda r: r.get("date", ""), reverse=True)[:days]

def check_consecutive_losses():
    """检查是否连亏3天→返回 (frozen: bool, loss_days: int, reason: str)"""
    records = sorted(_atomic_read(P_L_FILE, []), key=lambda r: r.get("date", ""), reverse=True)
    
    consecutive = 0
    loss_dates = []
    for r in records:
        if r.get("pnl", 0) < 0 and r.get("trades", 0) > 0:
            consecutive += 1
            loss_dates.append(r["date"])
        else:
            break
    
    if consecutive >= MAX_CONSECUTIVE_LOSS_DAYS:
        return True, consecutive, f"连亏{consecutive}天({','.join(loss_dates[:3])})→触发冻结"
    
    return False, consecutive, ""

def check_warning_level(consecutive_losses, daily_pnl, capital):
    """分级预警"""
    if consecutive_losses >= 5:
        return 'freeze', '策略冻结24h(连亏5天)'
    elif consecutive_losses >= 3:
        return 'halve', '仓位减半(连亏3天)'
    elif daily_pnl < -capital * 0.05:
        return 'warn', '单日亏损>5%, 次日仅1笔'
    return 'ok', '正常'

# ── 策略冻结 ──
def is_strategy_frozen():
    """检查策略是否被冻结"""
    state = _atomic_read(FREEZE_FILE, {"frozen_until": None, "reason": "", "frozen_at": None})
    
    frozen_until = state.get("frozen_until")
    if not frozen_until:
        return False, ""
    
    try:
        until = datetime.fromisoformat(frozen_until)
        if datetime.now() < until:
            remaining = until - datetime.now()
            hours = remaining.total_seconds() / 3600
            return True, f"策略冻结中({state.get('reason','')}) 剩余{hours:.1f}h 至{until.strftime('%m/%d %H:%M')}"
        else:
            # 解冻
            _atomic_write(FREEZE_FILE, {"frozen_until": None, "reason": "", "frozen_at": None, "thawed_at": datetime.now().isoformat()})
            return False, "已自动解冻"
    except:
        return False, ""

def freeze_strategy(reason="连亏3天自动冻结"):
    """冻结策略24小时"""
    frozen_until = (datetime.now() + timedelta(hours=FREEZE_DURATION_HOURS)).isoformat()
    state = {
        "frozen_until": frozen_until,
        "reason": reason,
        "frozen_at": datetime.now().isoformat(),
        "thawed_at": None
    }
    _atomic_write(FREEZE_FILE, state)
    return frozen_until

def unfreeze_strategy():
    """手动解冻"""
    _atomic_write(FREEZE_FILE, {"frozen_until": None, "reason": "", "frozen_at": None, "thawed_at": datetime.now().isoformat()})

def get_freeze_status():
    """获取冻结状态(用于进化报告)"""
    state = _atomic_read(FREEZE_FILE, {})
    frozen, reason = is_strategy_frozen()
    
    records = get_recent_pnl(10)
    total_pnl = sum(r.get("pnl", 0) for r in records)
    loss_days = sum(1 for r in records if r.get("pnl", 0) < 0)
    
    return {
        "is_frozen": frozen,
        "reason": reason or state.get("reason", ""),
        "frozen_until": state.get("frozen_until"),
        "frozen_at": state.get("frozen_at"),
        "recent_10d_pnl": round(total_pnl, 2),
        "recent_10d_loss_days": loss_days,
        "consecutive_loss_days": check_consecutive_losses()[1]
    }

# ── 时间止损(持仓>3天未盈利) ──  
def check_time_stop(positions, entry_dates, dry_run=True):
    """
    检查时间止损: 持仓>3天未盈利 → 强制平仓
    positions: {code: {profit_pct, ...}}
    entry_dates: {code: "YYYY-MM-DD"}
    返回 [(code, reason), ...]
    """
    if dry_run:
        return []
    
    today = datetime.now().strftime("%Y-%m-%d")
    time_stops = []
    
    for code, pos in positions.items():
        entry_date = entry_dates.get(code, "")
        if not entry_date:
            continue
        
        try:
            held_days = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(entry_date, "%Y-%m-%d")).days
        except:
            continue
        
        profit_pct = pos.get("profit_pct", 0)
        
        if held_days >= TIME_STOP_DAYS and profit_pct <= 0:
            time_stops.append((code, f"时间止损: 持仓{held_days}天未盈利({profit_pct:+.1f}%)"))
    
    return time_stops

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "status":
            frozen, reason = is_strategy_frozen()
            print(f"冻结状态: {'🔴 已冻结' if frozen else '🟢 正常'}")
            if frozen: print(f"  原因: {reason}")
            records = get_recent_pnl(10)
            pnl_items = [r['date'] + ' ¥' + f"{r['pnl']:+.0f}" for r in records[:5]]
            print(f"  近10日: {pnl_items}")
            has_losses, n, reason2 = check_consecutive_losses()
            print(f"  连亏检查: {n}天 {'⚠️触发' if has_losses else '✅安全'}")
        elif cmd == "freeze":
            until = freeze_strategy("手动冻结")
            print(f"🔴 策略已冻结至 {until}")
        elif cmd == "unfreeze":
            unfreeze_strategy()
            print("🟢 策略已解冻")
        elif cmd == "record":
            pnl = float(sys.argv[2]) if len(sys.argv) > 2 else 0
            record_daily_pnl(pnl=pnl, trade_count=1)
            print(f"📊 记录盈亏 ¥{pnl:+.0f}")
        else:
            print(f"用法: freeze_guard.py [status|freeze|unfreeze|record <pnl>]")
    else:
        print("策略冻结守卫 V1.0")
        print(f"  连亏{MAX_CONSECUTIVE_LOSS_DAYS}天→冻结{FREEZE_DURATION_HOURS}h")
        print(f"  时间止损: 持仓>{TIME_STOP_DAYS}天未盈利→强制平仓")
