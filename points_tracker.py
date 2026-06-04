#!/usr/bin/env python3
"""
积分实时追踪器 — 每次调用后显示: 已用/剩余
"""
import os, json, glob
from datetime import date
from pathlib import Path

MX_DIR = os.path.expanduser("~/.openclaw-autoclaw/workspace/mx_data/output")
STATE_FILE = os.path.expanduser("~/.openclaw-autoclaw/workspace/monitor/quota_state.json")
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

QUOTA = {"xuangu": 200, "data": 100, "search": 50, "zixuan": 20, "moni": 100}

def count_today():
    """快速统计今日各类型API调用"""
    today = date.today().isoformat()
    counts = {"xuangu": 0, "data": 0, "search": 0, "zixuan": 0, "moni": 0}
    
    for f in glob.glob(f"{MX_DIR}/mx_*.json"):
        try:
            mtime = date.fromtimestamp(os.path.getmtime(f)).isoformat()
            if mtime != today:
                continue
            fname = os.path.basename(f)
            for key in counts:
                if key in fname:
                    counts[key] += 1
                    break
        except:
            pass
    return counts

def status():
    """返回积分状态摘要"""
    counts = count_today()
    
    lines = []
    total_used = 0
    total_quota = 0
    
    for skill in ["xuangu", "data", "search", "zixuan"]:
        used = counts.get(skill, 0)
        quota = QUOTA.get(skill, 0)
        remaining = quota - used
        pct = used / quota * 100 if quota > 0 else 0
        total_used += used
        total_quota += quota
        
        if pct >= 90:
            icon = "🔴"
        elif pct >= 70:
            icon = "🟠"
        elif pct >= 50:
            icon = "🟡"
        else:
            icon = "🟢"
        
        lines.append(f"{icon} mx-{skill}: {used}/{quota} (余{remaining})")
    
    remaining_total = total_quota - total_used
    pct_total = total_used / total_quota * 100 if total_quota > 0 else 0
    
    return {
        "total_used": total_used,
        "total_quota": total_quota,
        "total_remaining": remaining_total,
        "total_pct": round(pct_total, 1),
        "details": counts,
        "lines": lines,
        "status": "🔴" if pct_total >= 90 else "🟠" if pct_total >= 70 else "🟡" if pct_total >= 50 else "🟢"
    }

def quick_status():
    """一行状态"""
    s = status()
    return f"{s['status']} 积分 {s['total_used']}/{s['total_quota']} (余{s['total_remaining']})"

def full_status():
    """详细状态"""
    s = status()
    print(f"\n{'='*45}")
    print(f"  📊 积分追踪  {s['status']} 已用{s['total_used']}/{s['total_quota']} (余{s['total_remaining']}, {s['total_pct']}%)")
    print(f"{'='*45}")
    for line in s['lines']:
        print(f"  {line}")
    print(f"{'='*45}\n")
    return s

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    if cmd == "status":
        full_status()
    elif cmd == "quick":
        print(quick_status())
    elif cmd == "json":
        print(json.dumps(status(), ensure_ascii=False))
    else:
        print(quick_status())
