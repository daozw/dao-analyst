#!/usr/bin/env python3
"""
盘前全自动流程 V1.0 — 统一入口
═══════════════════════════════════════════
1. 查询MX持仓 → 微信通知
2. 清仓（仅止损>3%）
3. 通知清仓结果
4. 波段池自动交易
5. 通知买入结果
6. 输出当日汇总
═══════════════════════════════════════════
"""
import sys, os, json, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(BASE, ".venv/bin/python3")

def run(cmd, timeout=60):
    """运行命令并返回输出"""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, 
                       timeout=timeout, cwd=BASE)
    return r.stdout.strip()

def main():
    dry = "--real" not in sys.argv
    mode = "实盘" if not dry else "模拟"
    
    print(f"🌅 盘前流程 [{mode}] {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)
    
    # Step 1: 查询持仓
    print("\n📦 Step 1/4: 查询持仓...")
    if not dry:
        pos = run(f"{VENV_PY} -c \"from pipeline.autotrade import get_mx_positions; p,t,v=get_mx_positions(); print(f'持仓{len(p)}只 ¥{t:,.0f} 盈亏¥{v:+,.0f}'); [print(f'  {c} {d[chr(34)+chr(110)+chr(97)+chr(109)+chr(101)+chr(34)]} {d[chr(34)+chr(113)+chr(116)+chr(121)+chr(34)]}股 盈亏{d[chr(34)+chr(112)+chr(114)+chr(111)+chr(102)+chr(105)+chr(116)+chr(95)+chr(112)+chr(99)+chr(116)+chr(34)]:+.1f}%') for c,d in p.items()]\"")
        print(pos)
    
    # Step 2: 清仓
    print("\n🧹 Step 2/4: 清仓检查...")
    clear_cmd = f"{VENV_PY} pipeline/autotrade.py clear"
    if not dry:
        clear_cmd += " --real"
    clear_result = run(clear_cmd, timeout=90)
    print(clear_result)
    
    # Step 3: 自动交易
    print("\n🤖 Step 3/4: 自动交易...")
    trade_cmd = f"{VENV_PY} pipeline/autotrade.py"
    if not dry:
        trade_cmd += " --real"
    trade_result = run(trade_cmd, timeout=90)
    print(trade_result)
    
    # Step 4: 通知检查
    print("\n📬 Step 4/4: 通知队列...")
    alerts = run(f"{VENV_PY} pipeline/trade_notify.py pending")
    print(alerts)
    
    print("\n" + "=" * 50)
    print("✅ 盘前流程完成")

if __name__ == "__main__":
    main()
