#!/usr/bin/env python3
"""
每日量化工作流编排器 V1.0
一键执行: 盘前→盘中→盘后 全流程
"""
import sys, os, json
from datetime import datetime

BASE = os.path.expanduser("~/dao-analyst")

def run(cmd):
    """运行CLI命令并捕获输出"""
    import subprocess
    r = subprocess.run(
        ["/Users/sound/quant-research/daily_stock_analysis/.venv/bin/python3", f"{BASE}/cli.py"] + cmd.split(),
        capture_output=True, text=True, timeout=60,
        cwd=BASE
    )
    return r.stdout.strip() or r.stderr.strip()

def workflow_morning():
    """盘前流程: 政策+简报+扫描"""
    print("🌅 盘前工作流")
    print("=" * 50)
    
    print("\n1/4 模拟账户检查...")
    print(run("trade"))
    
    print("\n2/4 板块轮动扫描...")
    print(run("sector"))
    
    print("\n3/4 双模策略候选池...")
    print(run("dual"))
    
    print("\n4/4 六维增强评分...")
    print(run("enhance"))
    
    print("\n✅ 盘前流程完成")

def workflow_intraday():
    """盘中流程: 监控+信号"""
    print("📊 盘中监控")
    print("=" * 50)
    
    print("\n1/3 账户仪表盘...")
    print(run("trade"))
    
    print("\n2/3 持仓监控...")
    print(run("monitor"))
    
    print("\n3/3 热点扫描...")
    print(run("scan"))
    
    print("\n✅ 盘中监控完成")

def workflow_evening():
    """盘后流程: 复盘+总结"""
    print("🌙 盘后复盘")
    print("=" * 50)
    
    print("\n1/4 账户仪表盘...")
    print(run("trade"))
    
    print("\n2/4 板块轮动回顾...")
    print(run("sector"))
    
    print("\n3/4 策略回测更新...")
    print(run("backtest"))
    
    print("\n4/4 明日前瞻...")
    print("  检查自选股中放量+低位+即将突破的标的")
    
    print("\n✅ 盘后复盘完成")

def workflow_full():
    """完整日流程"""
    now = datetime.now()
    hour = now.hour
    
    if hour < 9:
        workflow_morning()
    elif hour < 15:
        workflow_intraday()
    else:
        workflow_evening()

# ═══════ CLI ═══════
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    
    modes = {
        "morning": workflow_morning,
        "intraday": workflow_intraday,
        "evening": workflow_evening,
        "auto": workflow_full,
        "full": workflow_full,
    }
    
    if mode in modes:
        modes[mode]()
    else:
        print("用法: python3 workflow.py [morning|intraday|evening|auto]")
