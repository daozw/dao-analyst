#!/usr/bin/env python3
"""
财报日历追踪 V1.0 — 季报/中报/年报自动调度
"""
import sys, os, json
from datetime import datetime, timedelta

CALENDAR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "earnings_calendar.json")

# A股财报披露时间窗口
SEASONS = {
    "Q1": {"name": "一季报", "start": "04-01", "end": "04-30", "peak": "04-15", "frequency": "daily"},
    "Q2": {"name": "中报",   "start": "07-01", "end": "08-31", "peak": "08-15", "frequency": "daily"},
    "Q3": {"name": "三季报", "start": "10-01", "end": "10-31", "peak": "10-20", "frequency": "daily"},
    "Q4": {"name": "年报",   "start": "01-01", "end": "04-30", "peak": "03-15", "frequency": "daily"},
}

def get_current_season():
    """判断当前处于哪个财报季"""
    today = datetime.now()
    current = []
    
    for key, s in SEASONS.items():
        start = datetime.strptime(f"{today.year}-{s['start']}", "%Y-%m-%d")
        end = datetime.strptime(f"{today.year}-{s['end']}", "%Y-%m-%d")
        
        # 年报跨年
        if key == "Q4" and today.month < 5:
            start = datetime.strptime(f"{today.year-1}-{s['start']}", "%Y-%m-%d")
        
        if start <= today <= end:
            # 距离高峰期天数
            peak = datetime.strptime(f"{start.year}-{s['peak']}", "%Y-%m-%d")
            days_to_peak = (peak - today).days
            current.append({
                "season": key,
                "name": s["name"],
                "start": start.strftime("%Y-%m-%d"),
                "end": end.strftime("%Y-%m-%d"),
                "peak": peak.strftime("%Y-%m-%d"),
                "days_to_peak": days_to_peak,
                "is_peak": abs(days_to_peak) <= 7,
                "frequency": s["frequency"],
                "days_left": (end - today).days,
            })
    
    return current

def get_recommended_frequency():
    """根据财报季返回推荐扫描频率"""
    seasons = get_current_season()
    if not seasons:
        return "weekly", "非财报季，每周扫描"
    
    s = seasons[0]
    if s["is_peak"]:
        return "daily", f"{s['name']}高峰期(距{s['peak']}{s['days_to_peak']}天)，每日扫描"
    elif s["days_left"] <= 15:
        return "daily", f"{s['name']}冲刺期(剩余{s['days_left']}天)，每日扫描"
    else:
        return "2daily", f"{s['name']}期间，每2天扫描"

def load_state():
    if os.path.exists(CALENDAR_FILE):
        return json.load(open(CALENDAR_FILE))
    return {"last_scan": None, "next_scan": None}

def save_state(state):
    os.makedirs(os.path.dirname(CALENDAR_FILE), exist_ok=True)
    with open(CALENDAR_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def should_scan_today():
    """判断今天是否应该扫描"""
    freq, reason = get_recommended_frequency()
    state = load_state()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    if state.get("last_scan") == today:
        return False, "今日已扫描"
    
    if freq == "daily":
        return True, reason
    elif freq == "2daily":
        # 每2天
        last = state.get("last_scan", "")
        if last:
            last_date = datetime.strptime(last, "%Y-%m-%d")
            if (datetime.now() - last_date).days >= 2:
                return True, reason
        else:
            return True, reason
        return False, "距上次扫描不足2天"
    elif freq == "weekly":
        last = state.get("last_scan", "")
        if last:
            last_date = datetime.strptime(last, "%Y-%m-%d")
            if (datetime.now() - last_date).days >= 7:
                return True, reason
        else:
            return True, reason
        return False, "距上次扫描不足7天"
    
    return True, reason

def mark_scanned():
    """标记今天已扫描"""
    state = load_state()
    state["last_scan"] = datetime.now().strftime("%Y-%m-%d")
    freq, _ = get_recommended_frequency()
    
    # 计算下次扫描时间
    if freq == "daily":
        next_date = datetime.now() + timedelta(days=1)
    elif freq == "2daily":
        next_date = datetime.now() + timedelta(days=2)
    else:
        next_date = datetime.now() + timedelta(days=7)
    
    state["next_scan"] = next_date.strftime("%Y-%m-%d")
    save_state(state)

def report():
    """输出财报季状态报告"""
    seasons = get_current_season()
    freq, reason = get_recommended_frequency()
    can_scan, scan_reason = should_scan_today()
    
    lines = ["📅 财报日历"]
    lines.append("=" * 40)
    
    if seasons:
        for s in seasons:
            lines.append(f"\n📍 {s['name']} ({s['start']} ~ {s['end']})")
            lines.append(f"   高峰: {s['peak']} | 剩余: {s['days_left']}天")
            lines.append(f"   扫描频率: {freq}")
    else:
        lines.append("\n📭 当前非财报季")
        lines.append("   下次: 中报 7月1日-8月31日")
    
    lines.append(f"\n⚙️ 推荐: {reason}")
    lines.append(f"📊 今日扫描: {'✅ 需要' if can_scan else '⏭️ 跳过'} ({scan_reason})")
    
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        can, reason = should_scan_today()
        if can:
            print(f"✅ 执行扫描: {reason}")
            # Trigger growth_screener
            import subprocess
            screener = os.path.join(os.path.dirname(os.path.abspath(__file__)), "growth_screener.py")
            subprocess.run([sys.executable, screener])
            mark_scanned()
        else:
            print(f"⏭️ 跳过: {reason}")
    else:
        print(report())
