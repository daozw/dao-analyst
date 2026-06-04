#!/usr/bin/env python3
"""
板块轮动引擎 V3.0
追踪板块资金轮动 + 强弱转换 + 轮动节奏
"""
import subprocess, os, sys, json, csv
from datetime import datetime, timedelta
from collections import defaultdict

MX_KEY = os.environ.get("MX_APIKEY", "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8")
ENV = {**os.environ, "MX_APIKEY": MX_KEY}
XG = os.path.expanduser("~/.openclaw-autoclaw/skills/mx-xuangu/mx_xuangu.py")
WORKSPACE = os.path.expanduser("~/.openclaw-autoclaw/workspace/mx_data/output")

def run_xuangu(query):
    """执行选股查询"""
    r = subprocess.run(
        ["python3", XG, query],
        capture_output=True, text=True, env=ENV, timeout=30
    )
    return r.returncode == 0

def get_latest_csv(pattern):
    """获取最新匹配的CSV文件"""
    import glob
    files = sorted(glob.glob(f"{WORKSPACE}/*{pattern}*.csv"),
                   key=lambda x: os.path.getmtime(x), reverse=True)
    return files[0] if files else None

def scan_sector_flow():
    """扫描板块资金流向"""
    sectors = {}
    
    # 行业板块涨幅排行
    run_xuangu("今日 东财行业分类二级 涨幅大于1% 按涨跌幅降序")
    f = get_latest_csv("涨幅大于1%")
    if f:
        with open(f, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                try:
                    sector = row.get("东财行业分类二级", "").strip()
                    if not sector: continue
                    chg = float(row.get("涨跌幅(%)", "0").replace("%", ""))
                    if sector not in sectors:
                        sectors[sector] = {"chg": 0, "count": 0, "stocks": []}
                    sectors[sector]["chg"] += chg
                    sectors[sector]["count"] += 1
                    sectors[sector]["stocks"].append(row.get("名称", "").strip())
                except:
                    pass
    
    for s in sectors:
        if sectors[s]["count"] > 0:
            sectors[s]["avg_chg"] = round(sectors[s]["chg"] / sectors[s]["count"], 2)
    
    return sectors

def classify_rotation(sectors):
    """判断轮动状态"""
    ranked = sorted(sectors.items(), key=lambda x: x[1]["avg_chg"], reverse=True)
    
    leading = [(n, d) for n, d in ranked[:5] if d["avg_chg"] > 2]
    lagging = [(n, d) for n, d in ranked[-5:] if d["avg_chg"] < -1]
    
    total_sectors = len(sectors)
    rising = sum(1 for _, d in sectors.items() if d["avg_chg"] > 0)
    hot_pct = rising / total_sectors * 100 if total_sectors > 0 else 0
    
    if hot_pct > 70:
        status = "🔥 普涨轮动"
        advice = "追涨风险低，但需防板块切换"
    elif hot_pct > 45:
        status = "📊 结构性轮动"
        advice = "跟随领涨板块，汰弱留强"
    elif hot_pct > 25:
        status = "❄️ 轮动降温"
        advice = "控制仓位，只做最强板块"
    else:
        status = "🧊 全面冷却"
        advice = "空仓或极轻仓，等待方向"
    
    return {
        "status": status, "advice": advice, "hot_pct": round(hot_pct, 1),
        "leading": leading, "lagging": lagging, "total": total_sectors
    }

if __name__ == "__main__":
    print("🔄 V3.0 板块轮动引擎")
    print("=" * 55)
    sectors = scan_sector_flow()
    rotation = classify_rotation(sectors)
    
    print(f"\n📊 板块轮动状态: {rotation['status']}")
    print(f"  热度: {rotation['hot_pct']}% ({rotation['total']}个板块)")
    print(f"  建议: {rotation['advice']}")
    
    print(f"\n🔥 领涨板块 TOP5:")
    for name, d in rotation["leading"]:
        stocks = ",".join(d["stocks"][:3])
        print(f"  {name:<14} 均{d['avg_chg']:+.1f}%  {d['count']}只 [{stocks}]")
    
    if rotation["lagging"]:
        print(f"\n❄️ 领跌板块:")
        for name, d in rotation["lagging"]:
            print(f"  {name:<14} 均{d['avg_chg']:+.1f}%  {d['count']}只")
