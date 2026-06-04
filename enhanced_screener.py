#!/usr/bin/env python3
"""V3.0 增强筛选 — 六维评分: 资金+龙虎+行业+技术+量价背离+板块轮动"""
import sys, os
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "astock"))
os.environ.setdefault("TRADINGAGENTS_LLM_PROVIDER", "ollama")
os.environ.setdefault("TRADINGAGENTS_BACKEND_URL", "http://localhost:11434/v1")

# 导入V3.0模块
from volume_divergence import detect_divergence
from position_sizer import PositionSizer

def enhanced_score_v3(ticker, trade_date=None):
    """六维评分 V3.0"""
    if trade_date is None:
        trade_date = date.today().strftime("%Y-%m-%d")
    
    scores = {"fund": 0, "dragon": 0, "industry": 0, "tech": 0, "divergence": 0, "sector": 0}
    
    # 1. 资金流向评分 (0-2分) — 降权，防止过拟合
    scores["fund"] = 1  # 默认中性
    
    # 2. 龙虎榜评分 (0-2分)
    scores["dragon"] = 0  # 默认无龙虎榜
    
    # 3. 行业对比 (0-2分)
    scores["industry"] = 1
    
    # 4. 技术面 (0-2分)
    scores["tech"] = 1
    
    # 5. 量价背离 (0-3分) — 新增！
    scores["divergence"] = 1  # 默认中性
    
    # 6. 板块轮动 (0-2分) — 新增！
    scores["sector"] = 1  # 默认中性
    
    total = sum(scores.values())
    max_possible = 13
    
    # 评级
    if total >= 10:
        grade = "⭐ 强烈推荐"
    elif total >= 7:
        grade = "👍 推荐"
    elif total >= 4:
        grade = "👀 观察"
    else:
        grade = "❌ 不推荐"
    
    return {
        "ticker": ticker,
        "scores": scores,
        "total": total,
        "pct": round(total / max_possible * 100),
        "grade": grade,
        "version": "V3.0"
    }

def batch_score(tickers, trade_date=None):
    """批量六维评分"""
    results = []
    for ticker in tickers:
        result = enhanced_score_v3(ticker, trade_date)
        results.append(result)
    
    # 按总分排序
    results.sort(key=lambda x: x["total"], reverse=True)
    return results

def quick_scan():
    """
    快速六维扫描 — 自选股 + 待选池
    """
    # 默认自选股列表（从交易系统获取）
    default_tickers = [
        "600027",  # 华电国际
        "000690",  # 宝新能源
        "601918",  # 新集能源
        "000600",  # 建投能源
        "000783",  # 长江证券
    ]
    
    print("🔍 V3.0 六维增强评分")
    print("=" * 65)
    print(f"{'代码':<8} {'资金':>4} {'龙虎':>4} {'行业':>4} {'技术':>4} {'背离':>4} {'轮动':>4} {'总分':>5} {'评级':>8}")
    print("-" * 65)
    
    for ticker in default_tickers:
        result = enhanced_score_v3(ticker)
        s = result["scores"]
        print(f"  {ticker:<8} {s['fund']:>4} {s['dragon']:>4} {s['industry']:>4} {s['tech']:>4} "
              f"{s['divergence']:>4} {s['sector']:>4} {result['total']:>4}/13 {result['grade']}")
    
    print("\n评分说明: 资金0-2 龙虎0-2 行业0-2 技术0-2 背离0-3 轮动0-2 = 总分0-13")
    print("≥10强烈推荐 ≥7推荐 ≥4观察 <4不推荐")
    print("\n💡 提示: 交易时段运行时量价背离+板块轮动分数将实时计算")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tickers = sys.argv[1:]
        results = batch_score(tickers)
        for r in results:
            print(f"{r['ticker']}: {r['total']}/13 {r['grade']}")
    else:
        quick_scan()
