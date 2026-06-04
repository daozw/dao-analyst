#!/usr/bin/env python3
"""
DAO分析师 CLI V3.1 — 全栈统一入口
═══════════════════════════════════════════════════════════
覆盖: 报告生成 / 市场扫描 / 板块轮动 / 量价背离 / 
      仓位管理 / 策略回测 / 模拟交易 / 盯盘监控
═══════════════════════════════════════════════════════════
"""
import sys, os
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

HELP = """
📊 DAO分析师 CLI V3.1
═══════════════════════════════════════════════════════════
  报告类:
    report  <ticker>      个股完整报告
    png     <ticker>      个股报告→PNG长图
    
  扫描类:
    scan                  全市场短线·热点·打板
    sector                板块轮动分析
    diverge <ticker>      量价背离检测
    
  交易类:
    trade                 模拟交易仪表盘
    buy    <code> <p> <q> 模拟买入
    sell   <code> <p> <q> 模拟卖出
    cancel <id> <code>    撤单
    pos                   持仓查询
    
  风控类:
    position              仓位管理分析
    risk                  投资组合风险检查
    
  评估类:
    monitor               持仓实时监控
    daily    [ticker]     每日个股分析
    enhance  [tickers...] 六维增强评分
    dual                  双模策略框架
    
  回测类:
    backtest              多策略对比回测
    
  盯盘:
    sched                 📦持仓调度
    riskmgr               🛡️统一止盈止损
    watch                 启动实时盯盘
    free                   🎯五源免费筛选
    heat                   🔥三平台热度聚合
    social                 🔥社交媒体热度排行
    nightly              🌙深夜情报站(全维度)
═══════════════════════════════════════════════════════════
"""

def run_script(script, *args):
    cmd = f"/Users/sound/quant-research/daily_stock_analysis/.venv/bin/python3 {os.path.join(BASE, script)} {' '.join(args)}"
    return os.system(cmd)

if len(sys.argv) < 2:
    print(HELP)
    sys.exit(0)

cmd = sys.argv[1]
rest = sys.argv[2:]

# ═══════ 报告类 ═══════
if cmd == "report":
    ticker = rest[0] if rest else "002015"
    run_script("draw_report.py", ticker)

elif cmd == "png":
    ticker = rest[0] if rest else "002015"
    run_script("render_png.py", ticker)

# ═══════ 扫描类 ═══════
elif cmd == "scan":
    mode = rest[0] if rest else "all"
    run_script("hot_scanner.py", mode)

elif cmd == "sector":
    run_script("sector_rotation.py")

elif cmd == "diverge":
    ticker = rest[0] if rest else None
    run_script("volume_divergence.py")

# ═══════ 交易类 ═══════
elif cmd == "trade":
    run_script("mx_bridge.py", "dashboard")

elif cmd == "buy":
    if len(rest) < 3:
        print("用法: python3 cli.py buy <code> <price> <qty>")
    else:
        run_script("mx_bridge.py", "buy", *rest)

elif cmd == "sell":
    if len(rest) < 3:
        print("用法: python3 cli.py sell <code> <price> <qty>")
    else:
        run_script("mx_bridge.py", "sell", *rest)

elif cmd == "cancel":
    run_script("mx_bridge.py", "cancel", *rest)

elif cmd == "pos":
    run_script("mx_bridge.py", "positions")

# ═══════ 风控类 ═══════
elif cmd == "position":
    run_script("position_sizer.py")

elif cmd == "risk":
    run_script("position_sizer.py")

# ═══════ 评估类 ═══════
elif cmd == "monitor":
    run_script("monitor.py", "check")

elif cmd == "daily":
    ticker = rest[0] if rest else None
    args = [ticker] if ticker else []
    run_script("daily_stock_analysis.py", *args)

elif cmd == "enhance":
    run_script("enhanced_screener.py", *rest)

elif cmd == "dual":
    run_script("dual_strategy.py")

# ═══════ 回测类 ═══════
elif cmd == "backtest":
    run_script("backtest_multi.py")

# ═══════ 盯盘 ═══════
elif cmd == "free":
    run_script("free_screener.py")

elif cmd == "heat":
    run_script("multi_heat.py")

elif cmd == "social":
    run_script("social_heat.py")

elif cmd == "nightly":
    run_script("nightly_brief.py")

elif cmd == "swap":
    run_script("swap_analyzer.py")

elif cmd == "sched":
    run_script("portfolio_scheduler.py")

elif cmd == "riskmgr":
    run_script("risk_manager.py")

elif cmd == "system":
    os.system("cat ~/dao-analyst/SYSTEM.md")

elif cmd == "audit":
    os.system("/Users/sound/quant-research/daily_stock_analysis/.venv/bin/python3 /tmp/system_audit.py")

elif cmd == "watch":
    run_script("live_watch.py")

else:
    print(f"❌ 未知命令: {cmd}")
    print(HELP)
