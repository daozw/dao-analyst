#!/usr/bin/env python3
"""TradingAgents 周末摘要 — 政策+行业方向,不选股"""
import os, sys, json
from datetime import date

sys.path.insert(0, os.path.expanduser("~/dao-analyst/astock"))
os.environ["OPENAI_API_KEY"] = "ollama"
os.environ["TRADINGAGENTS_LLM_PROVIDER"] = "ollama"
os.environ["TRADINGAGENTS_QUICK_THINK_LLM"] = "qwen2.5:3b"
os.environ["TRADINGAGENTS_DEEP_THINK_LLM"] = "qwen2.5:3b"
os.environ["TRADINGAGENTS_BACKEND_URL"] = "http://localhost:11434/v1"
os.environ["TRADINGAGENTS_OUTPUT_LANGUAGE"] = "Chinese"

from tradingagents.graph.trading_graph import TradingAgentsGraph

OUTPUT = os.path.expanduser("~/dao-analyst/data/live/relay_pending.txt")

def run_weekend_digest():
    """周末运行: 分析大盘方向 + 行业热点,写摘要到relay文件"""
    graph = TradingAgentsGraph()
    sectors = [
        ("上证指数", "sh000001"),
        ("深证成指", "sz399001")
    ]
    
    results = []
    for name, code in sectors:
        print(f"🔍 分析{name}...")
        try:
            r = graph.propagate(company_name=name, trade_date=date.today().isoformat())
            results.append(str(r.get('final_decision', ''))[:300])
        except Exception as e:
            results.append(f"分析失败:{str(e)[:50]}")
    
    # Write to relay file for WeChat push
    today = date.today().isoformat()
    lines = [f"🤖 AI周报 | {today}", ""]
    lines.append("━━ 大盘方向 ━━")
    for i, r in enumerate(results):
        lines.append(r[:200] if r else "数据不足")
    lines.append("")
    lines.append("📌 以上为AI摘要,仅供参考,不构成买卖建议")
    
    with open(OUTPUT, 'w') as f:
        f.write('\n'.join(lines))
    print(f"✅ 已写入: {OUTPUT}")

if __name__ == '__main__':
    run_weekend_digest()
