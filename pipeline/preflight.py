#!/usr/bin/env python3
"""开盘前系统就绪检查 — 周一08:55执行"""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check(label, ok, detail=""):
    print(f"  {'✅' if ok else '❌'} {label}" + (f": {detail}" if detail else ""))
    return ok

all_ok = True
print("🛫 DAO分析师 Pre-flight |", __import__('datetime').datetime.now().strftime('%H:%M'))
print()

# API连通性
print("📡 API通道:")
try:
    from trader import UnifiedTrader
    b = UnifiedTrader(strategy="board")
    r = b.balance()
    ok = r.get("code") == "200" or r.get("ok")
    all_ok &= check("MX打板通道", ok, "余额查询" + ("✅" if ok else "❌"))
except Exception as e:
    all_ok &= check("MX打板通道", False, str(e)[:60])

try:
    t = UnifiedTrader(strategy="band")
    r = t.balance()
    ok = r.get("ok", False)
    all_ok &= check("华泰波段通道", ok, "余额查询" + ("✅" if ok else "❌"))
except Exception as e:
    all_ok &= check("华泰波段通道", False, str(e)[:60])

# 文件完整性
print("\n📁 关键文件:")
files = [
    ("board_lightning.py", "~/dao-analyst/board_lightning.py"),
    ("autotrade.py", "~/dao-analyst/pipeline/autotrade.py"),
    ("trader.py", "~/dao-analyst/trader.py"),
    ("trade_config.json", "~/dao-analyst/data/trade_config.json"),
    ("watchlist.json", "~/dao-analyst/data/watchlist.json"),
]
for name, path in files:
    p = os.path.expanduser(path)
    ok = os.path.exists(p) and os.path.getsize(p) > 100
    all_ok &= check(name, ok)

# crontab节拍
print("\n⏰ crontab关键节拍:")
import subprocess
try:
    ct = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    for line, desc in [
        ("board_lightning.py", "竞价扫描"),
        ("board_lightning.py --execute", "竞价下单"),
        ("market_open.sh", "开盘"),
        ("band_monitor.sh", "波段交易"),
        ("auto_backtest.py", "盘后回测"),
    ]:
        ok = line in ct
        all_ok &= check(desc, ok)
except:
    check("crontab", False)

# 彩票数据
print("\n🎱 彩票:")
try:
    s = json.load(open(os.path.expanduser("~/dp-lottery/data/sync_status.json")))
    score = s.get("data_integrity_score", 0)
    all_ok &= check(f"数据完整性", score >= 90, f"{score}/100")
except:
    all_ok &= check("彩票数据", False)

# 周一清仓
print("\n🧹 周一清仓:")
cf = "/tmp/dao_board_candidates.json"
if os.path.exists(cf):
    all_ok &= check("旧候选文件已清除", False, "请手动 rm")
else:
    all_ok &= check("候选文件干净", True)

print(f"\n{'✅ 系统就绪' if all_ok else '❌ 有问题,请检查'}")
sys.exit(0 if all_ok else 1)
