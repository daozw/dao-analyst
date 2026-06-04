#!/usr/bin/env python3
"""TradingAgents 本地集成 - 使用 Ollama Qwen3"""

import os, sys, json, argparse

os.environ.setdefault("TRADINGAGENTS_LLM_PROVIDER", "ollama")
os.environ.setdefault("TRADINGAGENTS_DEEP_THINK_LLM", "qwen3:14b")
os.environ.setdefault("TRADINGAGENTS_QUICK_THINK_LLM", "qwen3:14b")
os.environ.setdefault("TRADINGAGENTS_BACKEND_URL", "http://localhost:11434/v1")
os.environ.setdefault("TRADINGAGENTS_OUTPUT_LANGUAGE", "Chinese")

from tradingagents.graph.trading_graph import TradingAgentsGraph
from datetime import date

def analyze_stock(ticker: str, stock_name: str = ""):
    print(f"\n{'='*60}")
    print(f"TradingAgents: {stock_name or ticker} ({ticker})")
    print(f"{'='*60}\n")
    graph = TradingAgentsGraph()
    today = date.today().isoformat()
    result = graph.propagate(
        company_name=stock_name or ticker,
        trade_date=today,
        asset_type="stock"
    )
    return result

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("ticker")
    p.add_argument("--name", default="")
    args = p.parse_args()
    result = analyze_stock(args.ticker, args.name)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
