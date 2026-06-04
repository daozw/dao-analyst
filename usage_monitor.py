#!/usr/bin/env python3
"""
积分消耗监控系统 V1.0
追踪: mx-* API调用 / Ollama推理 / 每日配额 / 预警
"""
import os, json, glob, re
from datetime import datetime, date, timedelta
from collections import defaultdict
from pathlib import Path

MX_DIR = os.path.expanduser("~/.openclaw-autoclaw/workspace/mx_data/output")
OLLAMA_LOG = os.path.expanduser("~/.ollama/logs/server.log")
MONITOR_DIR = os.path.expanduser("~/.openclaw-autoclaw/workspace/monitor")
os.makedirs(MONITOR_DIR, exist_ok=True)

# 预估每日配额
DAILY_QUOTA = {
    "xuangu": 200,   # 选股查询
    "data": 100,     # 数据查询
    "search": 50,    # 搜索
    "zixuan": 20,    # 自选股
}

class UsageMonitor:
    
    def __init__(self):
        self.today = date.today().isoformat()
        self.stats_file = os.path.join(MONITOR_DIR, f"usage_{self.today}.json")
        self.history_file = os.path.join(MONITOR_DIR, "history.json")
        
    # ═══════════════════════════════════
    # mx-* API 调用统计
    # ═══════════════════════════════════
    def count_mx_calls(self):
        """从 output 目录统计今日 mx API 调用"""
        counts = {"xuangu": 0, "zixuan": 0, "data": 0, "search": 0, "moni": 0}
        
        for f in glob.glob(f"{MX_DIR}/*.json"):
            fname = os.path.basename(f)
            # 只统计今天的文件
            mtime = os.path.getmtime(f)
            mdate = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            if mdate != self.today:
                continue
            
            if "mx_xuangu" in fname:
                counts["xuangu"] += 1
            elif "mx_zixuan" in fname:
                counts["zixuan"] += 1
            elif "mx_data" in fname:
                counts["data"] += 1
            elif "mx_search" in fname:
                counts["search"] += 1
            elif "mx_moni" in fname:
                counts["moni"] += 1
        
        # 同时统计所有历史文件（不计入今日）
        all_time = {"xuangu": 0, "zixuan": 0, "data": 0, "search": 0, "moni": 0}
        for f in glob.glob(f"{MX_DIR}/*.json"):
            fname = os.path.basename(f)
            if "mx_xuangu" in fname: all_time["xuangu"] += 1
            elif "mx_zixuan" in fname: all_time["zixuan"] += 1
            elif "mx_data" in fname: all_time["data"] += 1
            elif "mx_search" in fname: all_time["search"] += 1
            elif "mx_moni" in fname: all_time["moni"] += 1
        
        return counts, all_time
    
    # ═══════════════════════════════════
    # Ollama 用量统计
    # ═══════════════════════════════════
    def count_ollama_usage(self):
        """从 Ollama 日志统计推理用量"""
        if not os.path.exists(OLLAMA_LOG):
            return {"requests": 0, "models": {}, "estimated_tokens": 0}
        
        models = defaultdict(int)
        total_requests = 0
        
        with open(OLLAMA_LOG, 'r') as f:
            for line in f:
                try:
                    # 只统计今天的
                    if self.today not in line:
                        continue
                    
                    # 统计请求
                    if "completion" in line.lower() or "chat" in line.lower():
                        total_requests += 1
                    
                    # 提取模型名
                    for model in ["qwen3", "deepseek-r1", "llama"]:
                        if model in line.lower():
                            models[model] += 1
                except:
                    pass
        
        # 粗略估算 token (每请求约1000 token)
        estimated = total_requests * 1000
        
        return {
            "requests": total_requests,
            "models": dict(models),
            "estimated_tokens": estimated
        }
    
    # ═══════════════════════════════════
    # 配额检查
    # ═══════════════════════════════════
    def quota_check(self, counts):
        """检查是否接近配额上限"""
        alerts = []
        
        for skill, count in counts.items():
            if skill not in DAILY_QUOTA:
                continue
            quota = DAILY_QUOTA[skill]
            pct = count / quota * 100 if quota > 0 else 0
            
            if pct >= 90:
                alerts.append({"level": "🔴", "skill": f"mx-{skill}", 
                              "msg": f"配额用尽 {count}/{quota} ({pct:.0f}%)"})
            elif pct >= 70:
                alerts.append({"level": "🟠", "skill": f"mx-{skill}",
                              "msg": f"配额紧张 {count}/{quota} ({pct:.0f}%)"})
            elif pct >= 50:
                alerts.append({"level": "🟡", "skill": f"mx-{skill}",
                              "msg": f"配额过半 {count}/{quota} ({pct:.0f}%)"})
        
        return alerts
    
    # ═══════════════════════════════════
    # 日报存盘
    # ═══════════════════════════════════
    def save_daily(self, counts, ollama, alerts):
        """保存每日统计"""
        data = {
            "date": self.today,
            "timestamp": datetime.now().isoformat(),
            "mx_calls": counts,
            "ollama": ollama,
            "alerts": alerts,
            "total_mx": sum(counts.values()),
            "total_ollama_requests": ollama["requests"],
            "quota_status": {
                sk: {"used": counts.get(sk, 0), "quota": q, 
                     "pct": round(counts.get(sk, 0)/q*100, 1) if q > 0 else 0}
                for sk, q in DAILY_QUOTA.items()
            }
        }
        
        with open(self.stats_file, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 更新历史
        history = []
        if os.path.exists(self.history_file):
            with open(self.history_file) as f:
                history = json.load(f)
        
        # 只保留30天
        history = [h for h in history if h["date"] != self.today]
        history.append({
            "date": self.today,
            "total_mx": data["total_mx"],
            "total_ollama": data["total_ollama_requests"],
            "alerts_count": len(alerts)
        })
        history = history[-30:]
        
        with open(self.history_file, 'w') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        return data
    
    # ═══════════════════════════════════
    # 完整仪表盘
    # ═══════════════════════════════════
    def dashboard(self):
        """积分消耗仪表盘"""
        mx_today, mx_all = self.count_mx_calls()
        ollama = self.count_ollama_usage()
        alerts = self.quota_check(mx_today)
        
        total_mx = sum(mx_today.values())
        
        # 预估每日消耗
        # 每条Cron job大约消耗: policy=5search, morning=10data+5xuangu, 
        # intraday=36次(每10分钟×2次)×4小时=72次, evening=10data+5search
        cron_estimate = 5 + 15 + 72 + 15  # ≈107次/天
        
        print("=" * 60)
        print("  📊 积分消耗监控仪表盘")
        print(f"  📅 {self.today}")
        print("=" * 60)
        
        print(f"\n📡 mx-* API 调用")
        print(f"  {'类型':<12} {'今日':>6} {'配额':>6} {'占比':>6} {'累计':>6} {'状态':>8}")
        print(f"  {'-'*44}")
        for skill in ["xuangu", "data", "search", "zixuan"]:
            used = mx_today.get(skill, 0)
            quota = DAILY_QUOTA.get(skill, 0)
            pct = used / quota * 100 if quota > 0 else 0
            all_t = mx_all.get(skill, 0)
            
            if pct >= 90:
                status = "🔴 告警"
            elif pct >= 70:
                status = "🟠 紧张"
            elif pct >= 50:
                status = "🟡 关注"
            else:
                status = "🟢 正常"
            
            bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            print(f"  {skill:<12} {used:>4}   {quota:>4}   {pct:>4.0f}% {bar} {status}")
        print(f"  {'总计':<12} {total_mx:>4}")
        
        print(f"\n🧠 Ollama 本地推理")
        print(f"  今日请求: {ollama['requests']}")
        print(f"  估算Token: ~{ollama['estimated_tokens']:,}")
        if ollama['models']:
            for m, c in ollama['models'].items():
                print(f"  {m}: {c}次")
        
        print(f"\n⚡ 预估消耗")
        print(f"  Cron自动化: ~{cron_estimate}次/交易日")
        print(f"  今日已用:   {total_mx}次")
        print(f"  工作日预估: {total_mx - cron_estimate:+d}次偏差")
        
        if alerts:
            print(f"\n🚨 配额预警 ({len(alerts)}条)")
            for a in alerts:
                print(f"  {a['level']} {a['skill']}: {a['msg']}")
        else:
            print(f"\n✅ 配额充足，无预警")
        
        # 历史趋势
        if os.path.exists(self.history_file):
            with open(self.history_file) as f:
                history = json.load(f)
            if len(history) >= 2:
                print(f"\n📈 近7天趋势")
                for h in history[-7:]:
                    bar_len = min(h['total_mx'] // 5, 40)
                    bar = "█" * bar_len
                    print(f"  {h['date']}  {h['total_mx']:>4}次 {bar}")
        
        # 优化建议
        print(f"\n💡 优化建议")
        if mx_today["xuangu"] > 100:
            print(f"  ⚠️ 选股调用过多({mx_today['xuangu']}次)，建议合并查询条件")
        print(f"  1. Cron已设为每10分钟检查，可放宽到15分钟")
        print(f"  2. 合并多个选股条件为一次查询")
        print(f"  3. 盘前/盘后集中查询，盘中仅异常推送")
        
        # 预估配额消耗天数
        daily_usage = total_mx - cron_estimate if total_mx > cron_estimate else cron_estimate
        print(f"\n🔮 基于今日模式，工作日每日消耗约 {daily_usage} 次")
        print(f"   建议预设配额警戒线: 150次/日")
        
        # 保存
        self.save_daily(mx_today, ollama, alerts)
        
        return {
            "mx_today": mx_today,
            "ollama": ollama,
            "alerts": alerts,
            "total": total_mx
        }

# ═══════════════════════════════════
# CLI
# ═══════════════════════════════════
if __name__ == "__main__":
    import sys
    m = UsageMonitor()
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dashboard"
    
    if cmd == "dashboard":
        m.dashboard()
    elif cmd == "alerts":
        mx, _ = m.count_mx_calls()
        alerts = m.quota_check(mx)
        if alerts:
            for a in alerts:
                print(f"{a['level']} {a['msg']}")
        else:
            print("✅ 无预警")
    elif cmd == "history":
        if os.path.exists(m.history_file):
            with open(m.history_file) as f:
                history = json.load(f)
            for h in history[-14:]:
                print(f"{h['date']}: mx={h['total_mx']} ollama={h['total_ollama']} alerts={h['alerts_count']}")
    elif cmd == "clean":
        # 清理7天前的mx_data缓存
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        cleaned = 0
        for f in glob.glob(f"{MX_DIR}/*"):
            if os.path.getmtime(f) < datetime.strptime(cutoff, "%Y-%m-%d").timestamp():
                os.remove(f)
                cleaned += 1
        print(f"🧹 清理了 {cleaned} 个过期文件 (>{cutoff})")
    else:
        print("用法: python3 usage_monitor.py [dashboard|alerts|history|clean]")
