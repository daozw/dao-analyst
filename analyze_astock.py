#!/usr/bin/env python3
"""TradingAgents A股版 — 7分析师 + 本地Ollama"""

import os, sys, json, argparse

# 使用 A 股版
sys.path.insert(0, os.path.expanduser("~/dao-analyst/astock"))

os.environ.setdefault("TRADINGAGENTS_LLM_PROVIDER", "ollama")
os.environ.setdefault("TRADINGAGENTS_DEEP_THINK_LLM", "qwen3.6:27b")
os.environ.setdefault("TRADINGAGENTS_QUICK_THINK_LLM", "qwen3.6:27b")
os.environ.setdefault("TRADINGAGENTS_BACKEND_URL", "http://localhost:11434/v1")
os.environ.setdefault("TRADINGAGENTS_OUTPUT_LANGUAGE", "Chinese")

from tradingagents.graph.trading_graph import TradingAgentsGraph
from datetime import date

def analyze(ticker: str, name: str = ""):
    print(f"\n{'='*60}")
    print(f"🔍 A股版7分析师: {name or ticker} ({ticker})")
    print(f"{'='*60}")
    print("分析师阵容: 市场 | 舆情 | 新闻 | 基本面 | 政策 | 游资 | 解禁")
    print(f"{'='*60}\n")

    graph = TradingAgentsGraph()
    result = graph.propagate(
        company_name=name or ticker,
        trade_date=date.today().isoformat(),
        asset_type="stock"
    )
    return result

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("ticker")
    p.add_argument("--name", default="")
    args = p.parse_args()
    result = analyze(args.ticker, args.name)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
