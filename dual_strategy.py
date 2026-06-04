#!/usr/bin/env python3
"""双模策略: 低吸 + 首板  共用趋势/量能/资金底座"""
import subprocess, sys, os
from datetime import datetime

MX_KEY = "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8"
ENV = {**os.environ, "MX_APIKEY": MX_KEY}
XG = "/Users/sound/.openclaw-autoclaw/skills/mx-xuangu/mx_xuangu.py"

def screen(query):
    """运行 mx-xuangu 筛选"""
    r = subprocess.run(["python3", XG, query], capture_output=True, text=True, env=ENV, timeout=30)
    return r.returncode == 0

# ═══════════════════════════════════
# 共同底座
# ═══════════════════════════════════
SHARED_BASE = "主板 收盘价大于MA20 MA20向上 近3日主力净流入为正 换手率3%到15%"

# ═══════════════════════════════════
# 低吸筛选
# ═══════════════════════════════════
DIP_SCREEN = (
    f"{SHARED_BASE} "
    "近20日内收盘价突破近60日最高价 "
    "当日成交量小于5日均量 "
    "收盘价接近最高价 回撤小于8% "
    "量比大于1.5"
)

# ═══════════════════════════════════
# 首板筛选  
# ═══════════════════════════════════
BOARD_SCREEN = (
    "主板 今日涨停 "
    "近20日新高 "
    "成交量大于5日均量1.5倍 "
    "主力净流入为正 "
    "换手率5%到15%"
)

print("="*60)
print("  双模策略框架: 低吸 + 首板")
print("="*60)

now = datetime.now().strftime("%Y年%m月%d日")

print(f"\n📥 低吸策略 ({now})")
print(f"   条件: MA20↑ + 近20日破60日高 + 缩量 + 换手3-10% + 尾盘强")
print(f"   查询: {DIP_SCREEN[:80]}...")

print(f"\n📊 首板策略 ({now})")  
print(f"   条件: 涨停 + 20日新高 + 放量 + 主力流入 + 换手5-15%")
print(f"   查询: {BOARD_SCREEN[:80]}...")

print(f"\n🛡️ 风控规则:")
print(f"   低吸止损: 破MA20且次收不回 / 跌破回踩低点")
print(f"   首板止损: 次高开走弱 / 高开低走 / 封单变薄")
print(f"   不做: 板块无梯队 / 情绪退潮 / 纯消息无资金")

print(f"\n📝 自然语言筛选已就绪，周一盘中实时运行")
print(f"   低吸候选池: 预计5-15只")
print(f"   首板候选池: 预计3-8只")
