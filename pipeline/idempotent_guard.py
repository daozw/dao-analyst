#!/usr/bin/env python3
"""幂等锁守卫 V1.0 — 同代码同方向300秒禁止重复提交 + 卖出前校验"""
import json, os, time, fcntl
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_FILE = os.path.join(BASE, "data", "state", "idempotent_lock.json")
LOCK_TTL = 300  # 5分钟

def _atomic_read():
    """线程安全读取锁文件"""
    try:
        with open(LOCK_FILE, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def _atomic_write(data):
    """线程安全写入锁文件"""
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    with open(LOCK_FILE, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def check_idempotent(code, direction, dry_run=True):
    """
    幂等检查: 同代码+同方向300秒内禁止重复
    返回 (allowed: bool, reason: str)
    """
    if dry_run:
        return True, ""
    
    now = time.time()
    locks = _atomic_read()
    
    # 清理过期锁
    cleaned = {k: v for k, v in locks.items() if now - v.get("ts", 0) < LOCK_TTL}
    
    key = f"{code}:{direction}"
    if key in cleaned:
        elapsed = int(now - cleaned[key]["ts"])
        return False, f"幂等锁: {code} {direction} {elapsed}s前已提交({LOCK_TTL}s内禁止重复)"
    
    # 添加新锁
    cleaned[key] = {"ts": now, "code": code, "direction": direction, "time": datetime.now().isoformat()}
    _atomic_write(cleaned)
    return True, ""

def verify_mx_position(code, mx_positions, action="SELL"):
    """
    卖出前校验: MX持仓是否真实存在
    返回 (exists: bool, qty: int, reason: str)
    """
    if action != "SELL":
        return True, 0, ""
    
    if code not in mx_positions:
        return False, 0, f"MX无{code}持仓, 拒绝卖出"
    
    pos = mx_positions[code]
    if pos.get("qty", 0) <= 0:
        return False, 0, f"MX持仓{code}已为0, 拒绝重复卖出"
    
    return True, pos["qty"], ""

def release_lock(code, direction):
    """手动释放锁(交易失败时)"""
    locks = _atomic_read()
    key = f"{code}:{direction}"
    locks.pop(key, None)
    _atomic_write(locks)

def list_active_locks():
    """列出活跃的幂等锁"""
    now = time.time()
    locks = _atomic_read()
    active = []
    for key, v in locks.items():
        age = now - v.get("ts", 0)
        if age < LOCK_TTL:
            active.append({**v, "age_seconds": int(age)})
    return active

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        locks = list_active_locks()
        print(f"活跃锁: {len(locks)}个")
        for l in locks:
            print(f"  {l['code']} {l['direction']} 剩余{LOCK_TTL - l['age_seconds']}s")
    elif len(sys.argv) > 1 and sys.argv[1] == "clear":
        _atomic_write({})
        print("✅ 幂等锁已清除")
    else:
        print(f"幂等锁守卫 V1.0 | TTL={LOCK_TTL}s")
        print(f"锁文件: {LOCK_FILE}")
